from typing import List, Tuple

import numpy as np

from two_stage_pipeliner.core.data import BboxData, ImageData
from two_stage_pipeliner.batch_generators.image_data import BatchGeneratorImageData
from two_stage_pipeliner.inference_models.detection.core import DetectionModel
from two_stage_pipeliner.core.inferencer import Inferencer


class DetectionInferencer(Inferencer):
    def __init__(self, model: DetectionModel):
        assert isinstance(model, DetectionModel)
        super().__init__(model)

    def _postprocess_predictions(
        self,
        images_data: List[ImageData],
        n_pred_cropped_images: List[List[np.ndarray]],
        n_pred_bboxes: List[List[Tuple[int, int, int, int]]],
        n_pred_scores: List[List[float]],
        open_images_in_images_data: bool
    ) -> List[ImageData]:

        pred_images_data = []
        for image_data, img_boxes, pred_bboxes, pred_scores in zip(
            images_data, n_pred_cropped_images, n_pred_bboxes, n_pred_scores
        ):
            bboxes_data = []
            for (pred_cropped_image, pred_bbox, pred_detection_score) in zip(img_boxes, pred_bboxes, pred_scores):
                ymin, xmin, ymax, xmax = pred_bbox
                bboxes_data.append(BboxData(
                    image_path=image_data.image_path,
                    image_bytes=image_data.image_bytes,
                    cropped_image=pred_cropped_image,
                    xmin=xmin,
                    ymin=ymin,
                    xmax=xmax,
                    ymax=ymax,
                    detection_score=pred_detection_score
                ))
            if open_images_in_images_data:
                image = image_data.image
            else:
                image = None
            pred_images_data.append(ImageData(
                image_path=image_data.image_path,
                image_bytes=image_data.image_bytes,
                image=image,
                bboxes_data=bboxes_data
            ))

        return pred_images_data

    def predict(
        self,
        images_data_gen: BatchGeneratorImageData,
        score_threshold: float,
        open_images_in_images_data: bool = False  # Warning: hard memory use
    ) -> List[ImageData]:

        pred_images_data = []
        for images_data in images_data_gen:
            input = [image_data.image for image_data in images_data]
            input = self.model.preprocess_input(input)
            n_pred_cropped_images, n_pred_bboxes, n_pred_scores = self.model.predict(
                input,
                score_threshold=score_threshold
            )
            pred_images_data_batch = self._postprocess_predictions(
                images_data, n_pred_cropped_images, n_pred_bboxes, n_pred_scores,
                open_images_in_images_data
            )
            pred_images_data.extend(pred_images_data_batch)

        return pred_images_data
