import json
import sys
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Callable, Union, ClassVar, Literal

import numpy as np
from tqdm import tqdm
import tensorflow as tf

from two_stage_pipeliner.inference_models.classification.core import (
    ClassificationModelSpec, ClassificationModel, ClassificationInput, ClassificationOutput
)


@dataclass(frozen=True)
class TensorFlow_ClassificationModelSpec(ClassificationModelSpec):
    input_size: Tuple[int, int]
    preprocess_input: Literal[Callable[[List[np.ndarray]], np.ndarray], Union[str, Path]]
    class_names: Literal[List[str], Union[str, Path]]
    model_path: Union[str, Path]
    saved_model_type: Literal["tf.saved_model", "tf.keras"]

    @property
    def inference_model(self) -> ClassVar['Tensorflow_ClassificationModel']:
        from two_stage_pipeliner.inference_models.classification.tensorflow import Tensorflow_ClassificationModel
        return Tensorflow_ClassificationModel


class Tensorflow_ClassificationModel(ClassificationModel):
    def _get_preprocess_input_from_script_file(
        self,
        script_file: Union[str, Path]
    ) -> Callable[[List[np.ndarray]], np.ndarray]:
        script_file = Path(script_file)
        sys.path.append(str(script_file.parent.absolute()))
        module = importlib.import_module(script_file.stem)
        sys.path.pop()
        return module.preprocess_input

    def load(
        self,
        model_spec: TensorFlow_ClassificationModelSpec
    ):
        assert isinstance(model_spec, TensorFlow_ClassificationModelSpec)
        super().load(model_spec)
        if isinstance(model_spec.class_names, str) or isinstance(model_spec.class_names, Path):
            with open(model_spec.class_names, 'r', encoding='utf-8') as out:
                self._class_names = json.load(out)
        else:
            self._class_names = model_spec.class_names
        if model_spec.saved_model_type == "tf.keras":
            self.model = tf.keras.models.load_model(str(model_spec.model_path))
            assert len(self._class_names) == int(self.model.output.shape[-1])
        elif model_spec.saved_model_type == "tf.saved_model":
            self.loaded_model = tf.saved_model.load(str(model_spec.model_path))
            self.model = self.loaded_model.signatures["serving_default"]
        else:
            raise ValueError(
                "Tensorflow_ClassificationModel got unknown saved_model_type "
                f"in TensorFlow_ClassificationModelSpec: {self.saved_model_type}"
            )

        if isinstance(model_spec.preprocess_input, str) or isinstance(model_spec.preprocess_input, Path):
            self._preprocess_input = self._get_preprocess_input_from_script_file(model_spec.preprocess_input)
        else:
            self._preprocess_input = model_spec.preprocess_input

        self.id_to_class_name = {
            id: class_name for id, class_name in enumerate(self._class_names)
        }
        self.batch_size = 16

        # Run model through a dummy image so that variables are created
        width, height = self.input_size
        zeros = np.zeros([1, width, height, 3])
        self._raw_predict_batch(zeros)

    def _raw_predict_batch(
        self,
        images: List[np.ndarray]
    ):
        if self.model_spec.saved_model_type == "tf.saved_model":
            input_tensor = tf.convert_to_tensor(images, dtype=tf.dtypes.float32)
            raw_predictions_batch = self.model(input_tensor)
        elif self.model_spec.saved_model_type == "tf.keras":
            raw_predictions_batch = self.model.predict(images)
        return raw_predictions_batch

    def _split_chunks(self,
                      _list: np.ndarray,
                      chunk_sizes: List[int]) -> List[np.ndarray]:
        cnt = 0
        chunks = []
        for chunk_size in chunk_sizes:
            chunks.append(_list[cnt: cnt + chunk_size])
            cnt += chunk_size
        return chunks

    def _raw_predict_all_batches(
        self,
        images: List[List[np.ndarray]],
        disable_tqdm: bool
    ) -> np.ndarray:

        predictions = []

        shapes = [len(sample_batch) for sample_batch in images]
        images = np.array(
            [item for sublist in images for item in sublist]
        )

        with tqdm(total=len(images), disable=disable_tqdm) as pbar:
            for i in range(0, len(images), self.batch_size):
                batch = images[i: i + self.batch_size]
                predictions_batch = self._raw_predict_batch(batch)
                predictions.append(predictions_batch)
                pbar.update(len(batch))

        predictions = np.concatenate(predictions)
        predictions = self._split_chunks(predictions, shapes)

        return predictions

    def _postprocess_predictions(self,
                                 predictions: np.ndarray) -> ClassificationOutput:

        max_scores_idxs = [np.argmax(pred, axis=1) for pred in predictions]
        pred_scores = [np.max(pred, axis=1) for pred in predictions]

        pred_labels = [
            [self.id_to_class_name[i] for i in pred_class]
            for pred_class in max_scores_idxs
        ]

        return pred_labels, pred_scores

    def predict(self,
                input: ClassificationInput,
                disable_tqdm: bool = False) -> ClassificationOutput:
        raw_prediction = self._raw_predict_all_batches(input, disable_tqdm=disable_tqdm)
        n_pred_labels, n_pred_scores = self._postprocess_predictions(raw_prediction)
        return n_pred_labels, n_pred_scores

    def preprocess_input(self, input: ClassificationInput):
        return [
            self._preprocess_input(cropped_images)
            for cropped_images in input
        ]

    @property
    def input_size(self) -> Tuple[int, int]:
        return self.model_spec.input_size

    @property
    def class_names(self) -> List[str]:
        return self._class_names
