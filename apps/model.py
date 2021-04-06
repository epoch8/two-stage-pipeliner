from cv_pipeliner.inference_models.pipeline import PipelineModelSpec
import imageio

from typing import Dict

from cv_pipeliner.core.data import ImageData
from cv_pipeliner.batch_generators.image_data import BatchGeneratorImageData
from cv_pipeliner.inference_models.detection.object_detection_api import (
    ObjectDetectionAPI_ModelSpec,
    ObjectDetectionAPI_pb_ModelSpec,
    ObjectDetectionAPI_TFLite_ModelSpec,
    ObjectDetectionAPI_KFServing
)
from cv_pipeliner.inference_models.classification.tensorflow import (
    TensorFlow_ClassificationModelSpec, TensorFlow_ClassificationModelSpec_TFServing
)
from cv_pipeliner.inference_models.classification.dummy import Dummy_ClassificationModelSpec
from cv_pipeliner.inferencers.pipeline import PipelineInferencer
from cv_pipeliner.utils.models_definitions import DetectionModelDefinition, ClassificationModelDefinition

from apps.config import (
    get_cfg_from_dict, CfgNode,
    object_detection_api,
    object_detection_api_pb,
    object_detection_api_tflite,
    object_detection_api_kfserving,
    tensorflow_cls_model,
    tensorflow_cls_model_kfserving,
    dummy_cls_model
)
# from apps.backend.src.realtime_inferencer import RealTimeInferencer


def get_detection_models_definitions_from_config(
    cfg: CfgNode
) -> DetectionModelDefinition:
    detection_models_definitions = []
    detection_models_indexes = []
    for detection_cfg in cfg.backend.models.detection:
        detection_cfg, key = get_cfg_from_dict(
            d=detection_cfg,
            possible_cfgs=[
                object_detection_api, object_detection_api_pb,
                object_detection_api_tflite, object_detection_api_kfserving
            ]
        )
        detection_model_definition = DetectionModelDefinition(
            description=detection_cfg.description,
            score_threshold=detection_cfg.score_threshold,
            model_spec=None,
            model_index=detection_cfg.model_index
        )
        if key == 'object_detection_api':
            detection_model_definition.model_spec = ObjectDetectionAPI_ModelSpec(
                config_path=detection_cfg.config_path,
                checkpoint_path=detection_cfg.checkpoint_path,
                class_names=detection_cfg.class_names
            )
        elif key == 'object_detection_api_pb':
            detection_model_definition.model_spec = ObjectDetectionAPI_pb_ModelSpec(
                saved_model_dir=detection_cfg.saved_model_dir,
                input_type=detection_cfg.input_type,
                class_names=detection_cfg.class_names
            )
        elif key == 'object_detection_api_tflite':
            detection_model_definition.model_spec = ObjectDetectionAPI_TFLite_ModelSpec(
                model_path=detection_cfg.model_path,
                bboxes_output_index=detection_cfg.bboxes_output_index,
                scores_output_index=detection_cfg.scores_output_index,
                class_names=detection_cfg.class_names
            )
        elif key == 'object_detection_api_kfserving':
            detection_model_definition.model_spec = ObjectDetectionAPI_KFServing(
                url=detection_cfg.url,
                input_name=detection_cfg.input_name,
                class_names=detection_cfg.class_names
            )
        detection_models_definitions.append(detection_model_definition)

    if len(set(detection_models_indexes)) != len(detection_models_indexes):
        raise ValueError('Detection model indexes in config file must be different.')

    return detection_models_definitions


def get_classification_models_definitions_from_config(
    cfg: CfgNode
) -> ClassificationModelDefinition:
    classification_models_definitions = []
    for classification_cfg in cfg.backend.models.classification:
        classification_cfg, key = get_cfg_from_dict(
            d=classification_cfg,
            possible_cfgs=[tensorflow_cls_model, tensorflow_cls_model_kfserving, dummy_cls_model]
        )
        classification_model_definition = ClassificationModelDefinition(
            description=classification_cfg.description,
            model_spec=None,
            model_index=classification_cfg.model_index
        )
        if key == 'tensorflow_cls_model':
            classification_model_definition.model_spec = TensorFlow_ClassificationModelSpec(
                input_size=classification_cfg.input_size,
                preprocess_input=classification_cfg.preprocess_input_script_file,
                class_names=classification_cfg.class_names,
                model_path=classification_cfg.model_path,
                saved_model_type=classification_cfg.saved_model_type
            )
        elif key == 'tensorflow_cls_model_kfserving':
            classification_model_definition.model_spec = TensorFlow_ClassificationModelSpec_TFServing(
                url=classification_cfg.url,
                input_name=classification_cfg.input_name,
                input_size=classification_cfg.input_size,
                preprocess_input=classification_cfg.preprocess_input_script_file,
                class_names=classification_cfg.class_names
            )
        elif key == 'dummy_cls_model':
            classification_model_definition.model_spec = Dummy_ClassificationModelSpec(
                default_class_name=classification_cfg.default_class_name
            )
        classification_models_definitions.append(classification_model_definition)

    return classification_models_definitions


def inference(
    pipeline_model_spec: PipelineModelSpec,
    image_data: ImageData,
    detection_score_threshold: float,
    classification_top_n: int
) -> ImageData:
    pipeline_model = pipeline_model_spec.load()
    pipeline_inferencer = PipelineInferencer(pipeline_model)
    image_data_gen = BatchGeneratorImageData(
        [image_data],
        batch_size=1,
        use_not_caught_elements_as_last_batch=True
    )
    pred_image_data = pipeline_inferencer.predict(
        image_data_gen,
        detection_score_threshold=detection_score_threshold,
        open_images_in_images_data=False,
        open_cropped_images_in_bboxes_data=False,
        classification_top_n=classification_top_n
    )[0]

    return pred_image_data


# def realtime_inference(
#     realtime_inferencer: RealTimeInferencer,
#     image_bytes: bytes,
#     detection_score_threshold: float,
#     batch_size: int = 16
# ) -> Dict:
#     image = imageio.imread(image_bytes, pilmode='RGB')
#     pred_bboxes_data = realtime_inferencer.predict_on_frame(
#         frame=image,
#         detection_score_threshold=detection_score_threshold,
#         batch_size=batch_size
#     )
#     pred_image_data = ImageData(bboxes_data=pred_bboxes_data)
#     json_res = pred_image_data.asdict()

#     return json_res