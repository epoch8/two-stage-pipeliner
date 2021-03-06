import time
import logging
from dataclasses import dataclass
from typing import List, Tuple
from multiprocessing import Process, Queue, Event

import numpy as np

from cv_pipeliner.core.data import ImageData, BboxData
from cv_pipeliner.batch_generators.image_data import BatchGeneratorImageData
from cv_pipeliner.batch_generators.bbox_data import BatchGeneratorBboxData
from cv_pipeliner.inference_models.detection.core import DetectionModelSpec
from cv_pipeliner.inferencers.detection import DetectionInferencer
from cv_pipeliner.inference_models.classification.core import ClassificationModelSpec
from cv_pipeliner.inferencers.classification import ClassificationInferencer

from cv_pipeliner.tracking.opencv_tracker import OpenCVTracker
from cv_pipeliner.tracking.sort_tracker import Sort


@dataclass
class FrameResult:
    label: str
    track_id: int
    ready_at_frame: int


@dataclass
class BboxDataTrackId:
    bbox_data: BboxData
    track_id: int


def classification_inferencer_queue(
    classification_model_spec: ClassificationInferencer,
    bbox_data_track_id_queue: Queue,
    ready_bbox_data_track_id_queue: Queue,
    loading_status_event: Event,
    status_event: Event,
    batch_size: int,
    time_sleep: float
):
    classification_model = classification_model_spec.load()
    classification_inferencer = ClassificationInferencer(classification_model)
    loading_status_event.set()
    while not status_event.is_set():
        if not bbox_data_track_id_queue.empty():
            current_batch_size = 0
            bboxes_data_tracks_ids = []
            while current_batch_size < batch_size and not bbox_data_track_id_queue.empty():
                bboxes_data_tracks_ids.append(bbox_data_track_id_queue.get(block=False))
                current_batch_size += 1
            bboxes_data_gen = BatchGeneratorBboxData(
                data=[[bbox_data_track_id.bbox_data] for bbox_data_track_id in bboxes_data_tracks_ids],
                batch_size=batch_size,
                use_not_caught_elements_as_last_batch=True
            )
            pred_bboxes_data = classification_inferencer.predict(bboxes_data_gen)[0]
            for pred_bbox_data, bbox_data_track_id in zip(pred_bboxes_data, bboxes_data_tracks_ids):
                ready_bbox_data_track_id_queue.put(
                    BboxDataTrackId(
                        bbox_data=BboxData(
                            xmin=bbox_data_track_id.bbox_data.xmin,
                            ymin=bbox_data_track_id.bbox_data.ymin,
                            xmax=bbox_data_track_id.bbox_data.xmax,
                            ymax=bbox_data_track_id.bbox_data.ymax,
                            label=pred_bbox_data.label
                        ),
                        track_id=bbox_data_track_id.track_id
                    )
                )
        else:
            time.sleep(time_sleep)


class RealTimeInferencer:
    def __init__(
        self,
        detection_model_spec: DetectionModelSpec,
        classification_model_spec: ClassificationModelSpec,
        fps: float,
        detection_delay: int,
        logger: logging.Logger,
        batch_size: int = 4,
        classification_time_sleep: float = 0.3
    ):
        self.classification_model_spec = classification_model_spec
        self.batch_size = batch_size
        self.classification_time_sleep = classification_time_sleep
        self.logger = logger

        self.logger.info("RealTimeInferencer: Loading detection model...")
        self.detection_model = detection_model_spec.load()
        self.detection_inferencer = DetectionInferencer(self.detection_model)

        self.bbox_data_track_id_queue = Queue()
        self.ready_bbox_data_track_id_queue = Queue()
        self.loading_status_event = Event()
        self.status_event = Event()
        self.classification_inferencer_process = Process(
            target=classification_inferencer_queue,
            args=(
                self.classification_model_spec,
                self.bbox_data_track_id_queue,
                self.ready_bbox_data_track_id_queue,
                self.loading_status_event,
                self.status_event,
                self.batch_size,
                self.classification_time_sleep
            )
        )
        self.logger.info("RealTimeInferencer: Loading classification model...")
        self.classification_inferencer_process.start()
        while not self.loading_status_event.is_set():
            time.sleep(self.classification_time_sleep)

        self.fps = fps
        self.detection_delay = detection_delay
        self.current_frame_idx = 0

        self.detection_delay_frames = int(round(self.detection_delay * fps / 1000))

        self.sort_tracker = Sort()
        self.opencv_tracker = None

        self.current_ready_frames_queue: List[FrameResult] = []

    def __del__(self):
        self.status_event.set()
        self.classification_inferencer_process.join()
        self.classification_inferencer_process.close()

    def update_sort_tracker(
        self,
        bboxes: List[Tuple[int, int, int, int]],
        scores: List[float] = None
    ) -> Tuple[List[Tuple[int, int, int, int]], List[int]]:
        if scores is None:
            # SORT requires detection scores, use 1 while tracking
            scores = np.ones(bboxes.shape[0])
        tracked_bboxes_sort = self.sort_tracker.update(
            np.column_stack([bboxes, scores])
        )
        tracked_bboxes_sort = tracked_bboxes_sort.round().astype(int)
        tracked_bboxes = tracked_bboxes_sort[:, :-1]
        tracked_bboxes = np.clip(tracked_bboxes, 0, tracked_bboxes.max(initial=0))
        tracked_ids = tracked_bboxes_sort[:, -1]
        return tracked_bboxes, tracked_ids

    def run_tracking_on_frame(
        self,
        frame: np.ndarray
    ) -> Tuple[List[Tuple[int, int, int, int]], List[int]]:
        tracked_bboxes_optical = self.opencv_tracker.update(frame)
        tracked_bboxes, tracked_ids = self.update_sort_tracker(
            bboxes=tracked_bboxes_optical
        )
        return tracked_bboxes, tracked_ids

    def run_pipeline_on_frame(
        self,
        frame: np.ndarray,
        detection_score_threshold: float,
        batch_size: int
    ) -> Tuple[List[Tuple[int, int, int, int]], List[int]]:
        frame = frame.copy()
        image_data = ImageData(image=frame)
        image_data_gen = BatchGeneratorImageData([image_data], batch_size=batch_size,
                                                 use_not_caught_elements_as_last_batch=True)

        pred_image_data = self.detection_inferencer.predict(
            images_data_gen=image_data_gen,
            score_threshold=detection_score_threshold
        )[0]
        bboxes = np.array([
            (bbox_data.xmin, bbox_data.ymin, bbox_data.xmax, bbox_data.ymax)
            for bbox_data in pred_image_data.bboxes_data
        ])
        detection_scores = np.array([bbox_data.detection_score for bbox_data in pred_image_data.bboxes_data])

        self.opencv_tracker = OpenCVTracker(bboxes, frame)
        tracked_bboxes, tracked_ids = self.update_sort_tracker(
            bboxes=bboxes, scores=detection_scores
        )

        current_tracks_ids = [frame_result.track_id for frame_result in self.current_ready_frames_queue]
        current_not_tracked_items_idxs = [
            idx for idx, tracked_id in enumerate(tracked_ids)
            if tracked_id not in current_tracks_ids
        ]
        if len(current_not_tracked_items_idxs) > 0:
            current_not_tracked_bboxes = tracked_bboxes[current_not_tracked_items_idxs]
            current_not_tracked_ids = tracked_ids[current_not_tracked_items_idxs]
            bboxes_data = [
                BboxData(image=frame, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
                for (xmin, ymin, xmax, ymax) in current_not_tracked_bboxes
            ]
            for bbox_data, tracked_id in zip(bboxes_data, current_not_tracked_ids):
                bbox_data_track_id = BboxDataTrackId(
                    bbox_data=bbox_data,
                    track_id=tracked_id
                )
                self.bbox_data_track_id_queue.put(bbox_data_track_id)
                frame_result = FrameResult(
                    label='...',
                    track_id=tracked_id,
                    ready_at_frame=self.current_frame_idx
                )
                self.current_ready_frames_queue.append(frame_result)

        return tracked_bboxes, tracked_ids

    def predict_on_frame(
        self,
        frame: np.ndarray,
        detection_score_threshold: float,
        batch_size: int
    ) -> List[BboxData]:
        if self.current_frame_idx % self.detection_delay_frames == 0:
            tracked_bboxes, tracked_ids = self.run_pipeline_on_frame(
                frame=frame,
                detection_score_threshold=detection_score_threshold,
                batch_size=batch_size
            )
        else:
            tracked_bboxes, tracked_ids = self.run_tracking_on_frame(frame)

        ready_frames_at_the_moment = [
            ready_frame
            for ready_frame in self.current_ready_frames_queue
            if ready_frame.ready_at_frame <= self.current_frame_idx
        ]
        ready_tracks_ids_at_the_moment = [
            ready_frame.track_id for ready_frame in ready_frames_at_the_moment
        ]
        ready_tracks_ids_at_the_moment_set = set(ready_tracks_ids_at_the_moment)

        if not self.ready_bbox_data_track_id_queue.empty():
            pred_bbox_data_track_id = self.ready_bbox_data_track_id_queue.get(block=False)
            pred_bbox_data = pred_bbox_data_track_id.bbox_data
            track_id = pred_bbox_data_track_id.track_id
            if track_id in ready_tracks_ids_at_the_moment_set:
                ready_frames_at_the_moment[
                    ready_tracks_ids_at_the_moment.index(track_id)
                ].label = pred_bbox_data.label

        bboxes_data = []
        for bbox, track_id in zip(tracked_bboxes, tracked_ids):
            if track_id not in ready_tracks_ids_at_the_moment_set:
                continue
            xmin, ymin, xmax, ymax = bbox
            ready_frame = ready_frames_at_the_moment[ready_tracks_ids_at_the_moment.index(track_id)]
            bboxes_data.append(BboxData(
                xmin=xmin,
                ymin=ymin,
                xmax=xmax,
                ymax=ymax,
                label=ready_frame.label
            ))
        self.current_frame_idx += 1
        return bboxes_data
