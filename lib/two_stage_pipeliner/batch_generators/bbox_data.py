from typing import List

from two_stage_pipeliner.core.data import BboxData
from two_stage_pipeliner.core.batch_generator import BatchGenerator


class BatchGeneratorBboxData(BatchGenerator):
    def __init__(self,
                 data: List[List[BboxData]],
                 batch_size: int,
                 use_not_caught_elements_as_last_batch: bool):
        assert all(isinstance(d, list) for d in data)
        assert all(isinstance(item, BboxData) for d in data for item in d)
        super().__init__(data, batch_size, use_not_caught_elements_as_last_batch)

    def __getitem__(self, index) -> List[List[BboxData]]:
        batch = super().__getitem__(index)
        for bboxes_data in batch:
            for bbox_data in bboxes_data:
                if bbox_data.cropped_image is None:
                    bbox_data.open_cropped_image(inplace=True)
        return batch
