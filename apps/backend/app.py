import sys
from pathlib import Path

import os
import logging

import tensorflow as tf

from dataclasses import dataclass, asdict
from typing import Dict

from flask import Flask, request, jsonify

from cv_pipeliner.inference_models.detection.core import DetectionModel
from cv_pipeliner.inference_models.classification.core import ClassificationModel
from cv_pipeliner.inference_models.pipeline import PipelineModel
from cv_pipeliner.inferencers.pipeline import PipelineInferencer
from cv_pipeliner.utils.models_definitions import DetectionModelDefinition, ClassificationDefinition

sys.path.insert(0, str(Path(__file__).absolute().parent.parent.parent))
from apps.backend.src.config import get_cfg_defaults  # noqa: E402
from apps.backend.src.realtime_inferencer import RealTimeInferencer  # noqa: E402
from apps.backend.src.model import (  # noqa: E402
    get_detection_models_definitions_from_config,
    get_classification_models_definitions_from_config,
    inference, realtime_inference
)

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
if 'CV_PIPELINER_BACKEND_MODEL_CONFIG' in os.environ:
    CONFIG_FILE = os.environ['CV_PIPELINER_BACKEND_MODEL_CONFIG']
else:
    app.logger.warning(
        "Environment variable 'CV_PIPELINER_BACKEND_MODEL_CONFIG' was not found. Loading default config instead."
    )
    CONFIG_FILE = 'config.yaml'
CURRENT_CONFIG_FILE_ST_MTIME = os.stat(CONFIG_FILE).st_mtime


def set_gpu():
    cfg = get_cfg_defaults()
    cfg.merge_from_file(CONFIG_FILE)
    cfg.freeze()
    if cfg.system.use_gpu:
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
        os.environ["CUDA_VISIBLE_DEVICES"] = "01"
    else:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""


@dataclass
class CurrentPipelineDefinition:
    detection_model_definition: DetectionModelDefinition = None
    classification_model_definition: ClassificationDefinition = None

    detection_model: DetectionModel = None
    classification_model: ClassificationModel = None
    pipeline_model: PipelineModel = None
    pipeline_inferencer: PipelineInferencer = None

    def reload(self):
        if self.detection_model is not None and self.classification_model is not None:
            self.pipeline_model = PipelineModel()
            self.pipeline_model.load_from_loaded_models(
                detection_model=self.detection_model,
                classification_model=self.classification_model
            )
            self.pipeline_inferencer = PipelineInferencer(self.pipeline_model)
CURRENT_PIPELINE_DEFINITION = CurrentPipelineDefinition()  # noqa: E305

@dataclass  # noqa: E302
class RealTimeInferencerData:
    guid: str
    realtime_inferencer: RealTimeInferencer
GUID_TO_REALTIME_INFERENCER_DATA = {}  # noqa: E305


@app.route('/get_available_models/', methods=['POST'])
def get_available_models():
    cfg = get_cfg_defaults()
    cfg.merge_from_file(CONFIG_FILE)
    cfg.freeze()
    detection_models_definitions = [
        asdict(detection_model_definition)
        for detection_model_definition in get_detection_models_definitions_from_config(cfg)
    ]
    classification_models_definitions = [
        asdict(classification_model_definition)
        for classification_model_definition in get_classification_models_definitions_from_config(cfg)
    ]
    return {
        'detection_models_definitions': detection_models_definitions,
        'classification_models_definitions': classification_models_definitions
    }


@app.route('/get_current_models/', methods=['POST'])
def get_current_models():
    detection_model_definition = asdict(CURRENT_PIPELINE_DEFINITION.detection_model_definition)
    classification_model_definition = asdict(CURRENT_PIPELINE_DEFINITION.classification_model_definition)
    return {
        'detection_model_definition': detection_model_definition,
        'classification_model_definition': classification_model_definition
    }


def set_detection_model(detection_model_index: str = None):
    cfg = get_cfg_defaults()
    cfg.merge_from_file(CONFIG_FILE)
    cfg.freeze()
    detection_models_definitions = get_detection_models_definitions_from_config(cfg)
    index_to_detection_model_definition = {
        detection_model_definition.model_index: detection_model_definition
        for detection_model_definition in detection_models_definitions
    }
    if detection_model_index is None:
        detection_model_index = detection_models_definitions[0].model_index
    else:
        if detection_model_index not in index_to_detection_model_definition:
            return jsonify(
                sucess=False,
                message=f'Detection model with index {detection_model_index} was not found in config file.'
            ), 400

    detection_model_definition = index_to_detection_model_definition[detection_model_index]
    app.logger.info(f"Loading detection model '{detection_model_definition.model_index}'...")
    CURRENT_PIPELINE_DEFINITION.detection_model_definition = detection_model_definition
    CURRENT_PIPELINE_DEFINITION.detection_model = detection_model_definition.model_spec.load()
    CURRENT_PIPELINE_DEFINITION.reload()

    app.logger.info("Detection model loaded sucessfully.")
    return jsonify(sucess=True)


@app.route('/set_classification_model/<classification_model_index>', methods=['POST'])
def set_classification_model(classification_model_index: str = None):
    cfg = get_cfg_defaults()
    cfg.merge_from_file(CONFIG_FILE)
    cfg.freeze()
    classification_models_definitions = get_classification_models_definitions_from_config(cfg)
    index_to_classification_model_definition = {
        classification_model_definition.model_index: classification_model_definition
        for classification_model_definition in classification_models_definitions
    }
    if classification_model_index is None:
        classification_model_index = classification_models_definitions[0].model_index
    else:
        if classification_model_index not in index_to_classification_model_definition:
            return jsonify(
                sucess=False,
                message=f'Classification model with index {classification_model_index} was not found in config file.'
            ), 400

    classification_model_definition = index_to_classification_model_definition[classification_model_index]
    app.logger.info(f"Loading classification model {classification_model_definition.model_index}...")
    CURRENT_PIPELINE_DEFINITION.classification_model_definition = classification_model_definition
    CURRENT_PIPELINE_DEFINITION.classification_model = classification_model_definition.model_spec.load()
    CURRENT_PIPELINE_DEFINITION.reload()
    app.logger.info("Classification model loaded sucessfully.")

    return jsonify(sucess=True)


# Load default models (first from config)
def load_from_config():
    with app.app_context():
        set_gpu()
        set_detection_model(detection_model_index=None)
        set_classification_model(classification_model_index=None)
load_from_config()  # noqa: E305


# --------------

@app.route('/predict', methods=['POST'])
def predict() -> Dict:
    if request.method == 'POST' and request.files.get('image', ''):
        detection_model_index = request.args.get(
            'detection_model_index', CURRENT_PIPELINE_DEFINITION.detection_model_definition.model_index
        )
        classification_model_index = request.args.get(
            'classification_model_index', CURRENT_PIPELINE_DEFINITION.classification_model_definition.model_index
        )
        if detection_model_index != CURRENT_PIPELINE_DEFINITION.detection_model_definition.model_index:
            set_detection_model(detection_model_index=detection_model_index)
        if classification_model_index != CURRENT_PIPELINE_DEFINITION.classification_model_definition.model_index:
            set_classification_model(classification_model_index=classification_model_index)
        detection_score_threshold = float(request.args.get(
            'detection_score_threshold', CURRENT_PIPELINE_DEFINITION.detection_model_definition.score_threshold
        ))
        res_json = inference(
            pipeline_inferencer=CURRENT_PIPELINE_DEFINITION.pipeline_inferencer,
            image_bytes=request.files.get('image', ''),
            detection_score_threshold=detection_score_threshold
        )
        return res_json
    return jsonify(success=False)


@app.route('/realtime_start/<guid>', methods=['POST'])
def realtime_start(guid: str) -> Dict:
    if request.method == 'POST':
        if guid in GUID_TO_REALTIME_INFERENCER_DATA:
            return jsonify(
                sucess=False,
                message='Realtime process with given guid is already started.'
            ), 400
        else:
            GUID_TO_REALTIME_INFERENCER_DATA[guid] = RealTimeInferencerData(
                guid=guid,
                realtime_inferencer=RealTimeInferencer(
                    detection_model_spec=CURRENT_PIPELINE_DEFINITION.detection_model_definition.model_spec,
                    classification_model_spec=CURRENT_PIPELINE_DEFINITION.classification_model_definition.model_spec,  # noqa: E501
                    fps=float(request.form['fps']),
                    detection_delay=int(request.form['detection_delay'])
                )
            )
            return jsonify(
                sucess=True,
                detection_model_definition=asdict(CURRENT_PIPELINE_DEFINITION.detection_model_definition),
                classification_model_definition=asdict(CURRENT_PIPELINE_DEFINITION.classification_model_definition)
            )


@app.route('/realtime_predict/<guid>', methods=['POST'])
def realtime_predict(guid: str) -> Dict:
    if request.method == 'POST' and request.files.get('image', '') and guid in GUID_TO_REALTIME_INFERENCER_DATA:
        res_json = realtime_inference(
            realtime_inferencer=GUID_TO_REALTIME_INFERENCER_DATA[guid].realtime_inferencer,
            image_bytes=request.files.get('image', ''),
            detection_score_threshold=CURRENT_PIPELINE_DEFINITION.detection_model_definition.score_threshold,
        )
        return res_json
    return jsonify(success=False, message='Realtime process with given guid is not started.'), 400


@app.route('/realtime_end/<guid>', methods=['POST'])
def realtime_end(guid: str) -> Dict:
    if request.method == 'POST':
        if guid not in GUID_TO_REALTIME_INFERENCER_DATA:
            return jsonify(sucess=False, message='Realtime process with given guid is not started.'), 400
        else:
            del GUID_TO_REALTIME_INFERENCER_DATA[guid]
            load_from_config()
            return jsonify(sucess=True)


@app.before_request
def before_request():
    config_file_st_mtime = os.stat(CONFIG_FILE).st_mtime
    global CURRENT_CONFIG_FILE_ST_MTIME
    if CURRENT_CONFIG_FILE_ST_MTIME != config_file_st_mtime:
        app.logger.info(
            "Config change detected. Reloading models..."
        )
        CURRENT_CONFIG_FILE_ST_MTIME = config_file_st_mtime
        load_from_config()


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response