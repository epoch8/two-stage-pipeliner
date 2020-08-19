from typing import List

from two_stage_pipeliner.core.data import BboxData, ImageData
from two_stage_pipeliner.core.batch_generator import BatchGeneratorImageData

from two_stage_pipeliner.core.inferencer import Inferencer
from two_stage_pipeliner.inference_models.pipeline import Pipeline


class PipelineInferencer(Inferencer):
    def __init__(self, model: Pipeline):
        assert isinstance(model, Pipeline)
        Inferencer.__init__(self, model)

    def predict(
        self,
        images_data_gen: BatchGeneratorImageData,
        detection_score_threshold: float,
        open_images_in_images_data: bool = False  # Warning: hard memory use
    ) -> List[ImageData]:
        pred_images_data = []
        for batch in images_data_gen:
            input = [image_data.image for image_data in batch]
            input = self.model.preprocess_input(input)
            (
                n_pred_cropped_images,
                n_pred_bboxes,
                n_pred_detection_scores,
                n_pred_labels,
                n_pred_classification_scores
            ) = self.model.predict(
                input,
                detection_score_threshold=detection_score_threshold
            )
            for (image_data, pred_cropped_images, pred_bboxes,
                 pred_detection_scores, pred_labels,
                 pred_classification_scores) in zip(
                     batch, n_pred_cropped_images, n_pred_bboxes,
                     n_pred_detection_scores, n_pred_labels,
                     n_pred_classification_scores
                 ):
                bboxes_data = []
                for (
                    pred_cropped_image,
                    pred_bbox,
                    pred_detection_score,
                    pred_label,
                    pred_classification_score
                ) in zip(
                    pred_cropped_images, pred_bboxes,
                    pred_detection_scores, pred_labels,
                    pred_classification_scores
                ):
                    ymin, xmin, ymax, xmax = pred_bbox
                    bboxes_data.append(BboxData(
                        image_path=image_data.image_path,
                        image_bytes=image_data.image_bytes,
                        cropped_image=pred_cropped_image,
                        xmin=xmin,
                        ymin=ymin,
                        xmax=xmax,
                        ymax=ymax,
                        detection_score=pred_detection_score,
                        label=pred_label,
                        classification_score=pred_classification_score
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
