from pathlib import Path
from typing import Tuple, Callable, Literal, List

import cv2
import imageio
import numpy as np
import imutils
from PIL import Image

from two_stage_pipeliner.core.data import BboxData, ImageData
from two_stage_pipeliner.metrics.image_data_matching import BboxDataMatching, ImageDataMatching

import streamlit as st


@st.cache(show_spinner=False)
def get_label_to_base_label_image(base_labels_images_dir) -> Callable[[str], np.ndarray]:
    base_labels_images_dir = Path(base_labels_images_dir)
    base_labels_images_paths = list(base_labels_images_dir.glob('*.png')) + list(base_labels_images_dir.glob('*.jp*g'))
    ann_class_names = [base_label_image_path.stem for base_label_image_path in base_labels_images_paths]
    unknown_image_filepath = None
    for candidate in ['unknown.png', 'unknown.jpg', 'unknown.jp*g']:
        if (base_labels_images_dir / candidate).exists():
            unknown_image_filepath = base_labels_images_dir / candidate
            break
    if unknown_image_filepath is None:
        raise ValueError('base_labels_images_dir must have unknown.png, unknown.jpg or unknown.jpeg.')

    unknown_image = np.array(imageio.imread(unknown_image_filepath))
    label_to_base_label_image_dict = {}
    for label in ann_class_names + ['unknown']:
        filepath = base_labels_images_dir / f"{label}.png"
        if filepath.exists():
            render = np.array(imageio.imread(filepath))
        else:
            render = unknown_image
        label_to_base_label_image_dict[label] = render

    def label_to_base_label_image(label: str) -> np.ndarray:
        if label in label_to_base_label_image_dict:
            return label_to_base_label_image_dict[label]
        else:
            return label_to_base_label_image_dict['unknown']

    return label_to_base_label_image


def concat_images(
    image_a: np.ndarray,
    image_b: np.ndarray,
    background_color_a: Tuple[int, int, int, int] = None,
    background_color_b: Tuple[int, int, int, int] = None,
    thumbnail_size_a: Tuple[int, int] = None,
    thumbnail_size_b: Tuple[int, int] = None
) -> np.ndarray:
    if image_a.shape[-1] == 3:
        image_a = cv2.cvtColor(image_a, cv2.COLOR_RGB2RGBA)
    if image_b.shape[-1] == 3:
        image_b = cv2.cvtColor(image_b, cv2.COLOR_RGB2RGBA)
    if thumbnail_size_a is not None:
        image_a = Image.fromarray(image_a)
        image_a.thumbnail(thumbnail_size_b)
        image_a = np.array(image_a)
    if thumbnail_size_b is not None:
        image_b = Image.fromarray(image_b)
        image_b.thumbnail(thumbnail_size_b)
        image_b = np.array(image_b)

    ha, wa = image_a.shape[:2]
    hb, wb = image_b.shape[:2]
    max_height = np.max([ha, hb])
    total_width = wa + wb

    min_ha = max_height // 2 - ha // 2
    max_ha = max_height // 2 + ha // 2
    min_hb = max_height // 2 - hb // 2
    max_hb = max_height // 2 + hb // 2

    new_image = np.zeros(shape=(max_height, total_width, 4), dtype=np.uint8)
    new_image[min_ha:max_ha, :wa, :] = image_a[0:(max_ha-min_ha), :]
    new_image[min_hb:max_hb, wa:wa+wb, :] = image_b[0:(max_hb-min_hb), :]

    if background_color_a is not None:
        new_image[:3, :wa, :] = background_color_a
        new_image[-3:, :wa, :] = background_color_a
        new_image[:, :3, :] = background_color_a
        new_image[:, wa-2:wa, :] = background_color_a
    if background_color_b is not None:
        new_image[:3, wa:, :] = background_color_b
        new_image[-3:, wa:, :] = background_color_b
        new_image[:, -3:, :] = background_color_b
        new_image[:, wa:wa+2, :] = background_color_b

    return new_image


@st.cache(show_spinner=False)
def get_illustrated_bboxes_data(
    bboxes_data: List[BboxData],
    label_to_base_label_image: Callable[[str], np.ndarray],
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    max_images_size: int = None
) -> Tuple[List[np.ndarray], List[str]]:
    cropped_images_and_renders = []
    cropped_images = [bbox_data.open_cropped_image() for bbox_data in bboxes_data]
    labels = [bbox_data.label for bbox_data in bboxes_data]
    renders = [label_to_base_label_image(label) for label in labels]
    for cropped_image, render in zip(cropped_images, renders):
        height, width, _ = cropped_image.shape
        size = max(height, width, 50)
        thumbnail_size_b = (size, size)
        cropped_image_and_render = concat_images(
            image_a=cropped_image,
            image_b=render,
            background_color_a=background_color_a,
            background_color_b=true_background_color_b,
            thumbnail_size_b=thumbnail_size_b
        )
        if max_images_size is not None:
            height, width, _ = cropped_image_and_render.shape
            if max(height, width) > max_images_size:
                if height <= width:
                    cropped_image_and_render = imutils.resize(cropped_image_and_render, width=max_images_size)
                else:
                    cropped_image_and_render = imutils.resize(cropped_image_and_render, height=max_images_size)

        cropped_images_and_renders.append(cropped_image_and_render)

    return cropped_images_and_renders, labels


@st.cache(show_spinner=False)
def get_illustrated_bboxes_data_matchings(
    bboxes_data_matchings: List[BboxDataMatching],
    label_to_base_label_image: Callable[[str], np.ndarray],
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    pred_background_color_b: Tuple[int, int, int, int] = None,
    max_images_size: int = None
) -> Tuple[List[np.ndarray], List[str]]:
    cropped_images_and_renders = []

    true_bboxes_data = [bbox_data_matching.true_bbox_data for bbox_data_matching in bboxes_data_matchings]
    pred_bboxes_data = [bbox_data_matching.pred_bbox_data for bbox_data_matching in bboxes_data_matchings]
    pred_cropped_images = [bbox_data.open_cropped_image() for bbox_data in pred_bboxes_data]
    true_labels = [bbox_data.label if bbox_data is not None else "unknown" for bbox_data in true_bboxes_data]
    pred_labels = [bbox_data.label for bbox_data in pred_bboxes_data]
    true_renders = [label_to_base_label_image(true_label) for true_label in true_labels]
    pred_renders = [label_to_base_label_image(pred_label) for pred_label in pred_labels]
    labels = [f"{pred_label}/{true_label}" for pred_label, true_label in zip(pred_labels, true_labels)]
    for cropped_image, true_render, pred_render in zip(pred_cropped_images, true_renders, pred_renders):
        height, width, _ = cropped_image.shape
        size = max(height, width, 50)
        thumbnail_size_b = (size, size)
        cropped_image_and_render = concat_images(
            image_a=cropped_image,
            image_b=pred_render,
            background_color_a=background_color_a,
            background_color_b=pred_background_color_b,
            thumbnail_size_b=thumbnail_size_b
        )
        cropped_image_and_render = concat_images(
            image_a=cropped_image_and_render,
            image_b=true_render,
            background_color_b=true_background_color_b,
            thumbnail_size_b=thumbnail_size_b
        )

        if max_images_size is not None:
            height, width, _ = cropped_image_and_render.shape
            if max(height, width) > max_images_size:
                if height <= width:
                    cropped_image_and_render = imutils.resize(cropped_image_and_render, width=max_images_size)
                else:
                    cropped_image_and_render = imutils.resize(cropped_image_and_render, height=max_images_size)

        cropped_images_and_renders.append(cropped_image_and_render)

    return cropped_images_and_renders, labels


@st.cache(show_spinner=False)
def get_image_data_matching(
    true_image_data: ImageData,
    pred_image_data: ImageData,
    minimum_iou: float
) -> ImageDataMatching:
    image_data_matching = ImageDataMatching(
        true_image_data=true_image_data,
        pred_image_data=pred_image_data,
        minimum_iou=minimum_iou
    )
    return image_data_matching


def illustrate_bboxes_data(
    true_image_data: ImageData,
    label_to_base_label_image: Callable[[str], np.ndarray],
    mode: Literal['many', 'one-by-one'],
    pred_image_data: ImageData = None,
    minimum_iou: float = None,
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    pred_background_color_b: Tuple[int, int, int, int] = None,
    average_maximum_images_per_page: int = 50,
    max_images_size: int = 400
):
    if pred_image_data is None:
        bboxes_data = true_image_data.bboxes_data
    else:
        assert minimum_iou is not None
        assert pred_background_color_b is not None
        image_data_matching = get_image_data_matching(
            true_image_data=true_image_data,
            pred_image_data=pred_image_data,
            minimum_iou=minimum_iou
        )
        bboxes_data = [
            bbox_data_matching for bbox_data_matching in image_data_matching.bboxes_data_matchings
            if bbox_data_matching.pred_bbox_data is not None
        ]

    if len(bboxes_data) == 0:
        return

    if pred_image_data is not None:
        st.text(f"Found {len(pred_image_data.bboxes_data)} bricks!")
        st.text(f"""
True Positives: {image_data_matching.get_pipeline_TP()}
False Positives: {image_data_matching.get_pipeline_FP()}
False Negatives: {image_data_matching.get_pipeline_FN()}

Extra bboxes counts: {image_data_matching.get_detection_FP()}
True Positives on extra bboxes: {image_data_matching.get_pipeline_TP_extra_bbox()}
False Positives on extra bboxes: {image_data_matching.get_pipeline_FP_extra_bbox()}""")
    else:
        st.text(f"Found {len(true_image_data.bboxes_data)} bricks!")

    n_split = int(np.ceil(len(bboxes_data) / average_maximum_images_per_page))
    splitted_bboxes_data = np.array_split(bboxes_data, n_split)

    if n_split >= 2:
        page = st.slider(
            label="",
            min_value=1,
            max_value=n_split
        )
        page_bboxes_data = splitted_bboxes_data[page-1]
    else:
        page_bboxes_data = splitted_bboxes_data[0]

    if pred_image_data is None:
        cropped_images_and_renders, labels = get_illustrated_bboxes_data(
            bboxes_data=page_bboxes_data,
            label_to_base_label_image=label_to_base_label_image,
            background_color_a=background_color_a,
            true_background_color_b=true_background_color_b,
            max_images_size=max_images_size
        )
    else:
        cropped_images_and_renders, labels = get_illustrated_bboxes_data_matchings(
            bboxes_data_matchings=page_bboxes_data,
            label_to_base_label_image=label_to_base_label_image,
            background_color_a=background_color_a,
            true_background_color_b=true_background_color_b,
            pred_background_color_b=pred_background_color_b,
            max_images_size=max_images_size
        )

    if mode == "one-by-one":
        for cropped_image_and_render, label in zip(cropped_images_and_renders, labels):
            st.image(image=cropped_image_and_render)
            st.markdown(label)
            st.markdown('----')
    elif mode == "many":
        st.image(image=cropped_images_and_renders, caption=labels)
        st.markdown('----')
