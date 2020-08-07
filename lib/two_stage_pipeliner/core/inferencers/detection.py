import abc

from two_stage_pipeliner.core.batch_generator import BatchGeneratorImageData, BatchGeneratorBboxData
from two_stage_pipeliner.core.inference_model import InferenceModel
from two_stage_pipeliner.core.inferencer import Inferencer


class DetectionModel(InferenceModel):
    def __init__(self):
        super(InferenceModel, self).__init__()


class DetectionInferencer(Inferencer):
    def __init__(self, model: DetectionModel):
        assert isinstance(model, DetectionModel)
        super(DetectionInferencer, self).__init__(model)

    @abc.abstractmethod
    def predict(self, data_generator: BatchGeneratorImageData) -> BatchGeneratorBboxData:
        pass
