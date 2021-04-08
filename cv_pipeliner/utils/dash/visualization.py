from typing import Tuple, Callable, List, Dict

import numpy as np
import imutils

import dash
import dash_core_components as dcc
import dash_html_components as html

from cv_pipeliner.core.data import BboxData, ImageData
from cv_pipeliner.metrics.image_data_matching import BboxDataMatching, ImageDataMatching
from cv_pipeliner.utils.images import concat_images, get_image_b64, open_image


def get_illustrated_bboxes_data(
    source_image: np.ndarray,
    bboxes_data: List[BboxData],
    label_to_base_label_image: Callable[[str], np.ndarray],
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    max_images_size: int = None,
    bbox_offset: int = 0,
    draw_rectangle_with_color: Tuple[int, int, int, int] = None,
    alpha: float = 0.3
) -> Tuple[List[np.ndarray], List[str]]:
    cropped_images_and_renders = []
    cropped_images = [
        bbox_data.open_cropped_image(
            source_image=source_image,
            xmin_offset=bbox_offset,
            ymin_offset=bbox_offset,
            xmax_offset=bbox_offset,
            ymax_offset=bbox_offset,
            draw_rectangle_with_color=draw_rectangle_with_color,
            alpha=alpha
        )
        for bbox_data in bboxes_data
    ]
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


def get_illustrated_bboxes_data_matchings(
    source_image: np.ndarray,
    bboxes_data_matchings: List[BboxDataMatching],
    label_to_base_label_image: Callable[[str], np.ndarray],
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    pred_background_color_b: Tuple[int, int, int, int] = None,
    max_images_size: int = None,
    bbox_offset: int = 0,
    draw_rectangle_with_color: Tuple[int, int, int] = None
) -> Tuple[List[np.ndarray], List[str]]:
    cropped_images_and_renders = []

    true_bboxes_data = [bbox_data_matching.true_bbox_data for bbox_data_matching in bboxes_data_matchings]
    pred_bboxes_data = [bbox_data_matching.pred_bbox_data for bbox_data_matching in bboxes_data_matchings]
    pred_cropped_images = [bbox_data.open_cropped_image(
        source_image=source_image,
        xmin_offset=bbox_offset,
        ymin_offset=bbox_offset,
        xmax_offset=bbox_offset,
        ymax_offset=bbox_offset,
        draw_rectangle_with_color=draw_rectangle_with_color
    ) for bbox_data in pred_bboxes_data]
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


def illustrate_bboxes_data(
    true_image_data: ImageData,
    label_to_base_label_image: Callable[[str], np.ndarray],
    label_to_description: Dict[str, str],
    pred_image_data: ImageData = None,
    minimum_iou: float = None,
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    pred_background_color_b: Tuple[int, int, int, int] = None,
    average_maximum_images_per_page: int = 20,
    current_page: int = 1,
    max_images_size: int = 400,
    bbox_offset: int = 0,
    draw_rectangle_with_color: Tuple[int, int, int] = None,
    show_top_n: bool = False,
):
    div_children_result = []

    source_image = true_image_data.open_image()

    if pred_image_data is None:
        bboxes_data = true_image_data.bboxes_data
        for idx, bbox_data in enumerate(bboxes_data):
            bbox_data.additional_info['idx'] = idx + 1
    else:
        assert minimum_iou is not None
        assert pred_background_color_b is not None
        image_data_matching = ImageDataMatching(
            true_image_data=true_image_data,
            pred_image_data=pred_image_data,
            minimum_iou=minimum_iou
        )
        bboxes_data = [
            bbox_data_matching for bbox_data_matching in image_data_matching.bboxes_data_matchings
            if bbox_data_matching.pred_bbox_data is not None
        ]
        for idx, bbox_data in enumerate(bboxes_data):
            bbox_data.pred_bbox_data.additional_info['idx'] = idx + 1

    if len(bboxes_data) == 0:
        return html.Div(children=div_children_result)

    if pred_image_data is not None:
        total_bboxes = len(pred_image_data.bboxes_data)
        div_children_result.extend([
            html.Center(
                children=[
                    dcc.Markdown(
                        f"Found **{total_bboxes}** bboxes total",
                        style={
                            'font-size': '25px'
                        }
                    ),
                    dcc.Markdown(f"""
* True Positives: {image_data_matching.get_pipeline_TP()}
* False Positives: {image_data_matching.get_pipeline_FP()}
* False Negatives: {image_data_matching.get_pipeline_FN()}
* Extra bboxes counts: {image_data_matching.get_detection_FP()}
* True Positives on extra bboxes: {image_data_matching.get_pipeline_TP_extra_bbox()}
* False Positives on extra bboxes: {image_data_matching.get_pipeline_FP_extra_bbox()}""",
                        style={  # noqa: E128
                            'font-size': '14px'
                        }
                    ),
                    html.Hr()
                ]
            ),
        ])
    else:
        total_bboxes = len(true_image_data.bboxes_data)
        div_children_result.append(
            html.Center(
                children=[
                    dcc.Markdown(
                        f"Found **{total_bboxes}** bboxes!",
                        style={
                            'font-size': '16px'
                        }
                    ),
                    html.Hr()
                ]
            ),
        )

    n_split = int(np.ceil(len(bboxes_data) / average_maximum_images_per_page))
    splitted_bboxes_data = np.array_split(bboxes_data, n_split)
    page_bboxes_data = splitted_bboxes_data[current_page-1]

    if pred_image_data is None:
        cropped_images_and_renders, labels = get_illustrated_bboxes_data(
            source_image=source_image,
            bboxes_data=page_bboxes_data,
            label_to_base_label_image=label_to_base_label_image,
            background_color_a=background_color_a,
            true_background_color_b=true_background_color_b,
            max_images_size=max_images_size,
            bbox_offset=bbox_offset,
            draw_rectangle_with_color=draw_rectangle_with_color
        )
    else:
        cropped_images_and_renders, labels = get_illustrated_bboxes_data_matchings(
            source_image=source_image,
            bboxes_data_matchings=page_bboxes_data,
            label_to_base_label_image=label_to_base_label_image,
            background_color_a=background_color_a,
            true_background_color_b=true_background_color_b,
            pred_background_color_b=pred_background_color_b,
            max_images_size=max_images_size,
            bbox_offset=bbox_offset,
            draw_rectangle_with_color=draw_rectangle_with_color
        )

    for cropped_image_and_render, label, bbox_data in zip(cropped_images_and_renders, labels, page_bboxes_data):
        main_div_children = []
        main_div_children.append(
            html.Img(
                src=f"data:image/png;base64,{get_image_b64(cropped_image_and_render, format='png')}",
                style={
                    'max-width': '600px',
                    'height': '100%'
                }
            )
        )
        bbox_div = []
        if isinstance(bbox_data, BboxData):
            bbox_div.extend([
                html.Br(),
                dcc.Markdown(
                    f"Bbox **{bbox_data.additional_info['idx']}/{total_bboxes}**"
                ),
                dcc.Markdown(
                    f"**'{label}'**",
                    style={
                        'font-size': '20px'
                    }
                ),
                dcc.Markdown(label_to_description[label]),
                dcc.Markdown(f'Bbox: {(bbox_data.xmin, bbox_data.ymin, bbox_data.xmax, bbox_data.ymax)}'),
            ])
            if bbox_data.detection_score is not None:
                bbox_div.append(
                    dcc.Markdown(f'Detection score: {bbox_data.detection_score}')
                )
            if bbox_data.classification_score is not None:
                bbox_div.append(
                    dcc.Markdown(f'Classification score: {bbox_data.classification_score}')
                )
            if show_top_n:
                bbox_div.extend([
                    dcc.Markdown(f'Top-n labels: {tuple(bbox_data.labels_top_n)}'),
                    dcc.Markdown(f'Top-n scores: {tuple(bbox_data.classification_scores_top_n)}')
                ])

        elif isinstance(bbox_data, BboxDataMatching):
            true_bbox_data = bbox_data.true_bbox_data
            pred_bbox_data = bbox_data.pred_bbox_data
            bbox_div.append(
                dcc.Markdown(
                    f"BboxDataMatching **{pred_bbox_data.additional_info['idx']}/{total_bboxes}**"
                )
            )
            if pred_bbox_data is not None:
                bbox_div.extend([
                    dcc.Markdown(f"**Prediction**: **'{pred_bbox_data.label}'**"),
                    dcc.Markdown(label_to_description[pred_bbox_data.label]),
                    dcc.Markdown(
                        f'Bbox: {(pred_bbox_data.xmin, pred_bbox_data.ymin, pred_bbox_data.xmax, pred_bbox_data.ymax)}'
                    )
                ])
                if pred_bbox_data.detection_score is not None:
                    bbox_div.append(
                        dcc.Markdown(f'Detection score: {pred_bbox_data.detection_score}')
                    )
                if pred_bbox_data.classification_score is not None:
                    bbox_div.append(
                        dcc.Markdown(f'Classification score: {pred_bbox_data.classification_score}')
                    )
                if show_top_n:
                    bbox_div.extend([
                        dcc.Markdown(f'Top-n labels: {tuple(pred_bbox_data.labels_top_n)}'),
                        dcc.Markdown(f'Top-n scores: {tuple(pred_bbox_data.classification_scores_top_n)}')
                    ])
                bbox_div.append(
                    html.Hr()
                )
            if true_bbox_data is not None:
                bbox_div.extend([
                    dcc.Markdown(f"**Ground Truth**: **'{true_bbox_data.label}'**"),
                    dcc.Markdown(label_to_description[true_bbox_data.label]),
                    dcc.Markdown(
                        f'Bbox: {(true_bbox_data.xmin, true_bbox_data.ymin, true_bbox_data.xmax, true_bbox_data.ymax)}'
                    )
                ])
                if show_top_n:
                    bbox_div.extend([
                        dcc.Markdown(f'Top-n labels: {tuple(pred_bbox_data.labels_top_n)}'),
                        dcc.Markdown(f'Top-n scores: {tuple(pred_bbox_data.classification_scores_top_n)}')
                    ])
                bbox_div.append(
                    html.Hr()
                )
            bbox_div.append(
                dcc.Markdown(f'Pipeline error type: {bbox_data.get_pipeline_error_type()}')
            )
        main_div_children.append(
            html.Div(
                children=bbox_div,
                style={
                    'border': '3px solid black',
                    'padding': '10px',
                    'max-width': '600px',
                    'margin-left': '30px'
                }
            )
        )
        div_children_result.append(
            html.Div(
                children=main_div_children,
                style={
                    'display': 'flex',
                    'justify-content': 'start',
                    'margin-top': '10px',
                    'max-width': '1000px'
                }
            )
        )
        div_children_result.append(
            html.Hr()
        )

    return html.Div(children=div_children_result)


def illustrate_n_bboxes_data(
    n_bboxes_data: List[List[BboxData]],
    label_to_base_label_image: Callable[[str], np.ndarray],
    label_to_description: Dict[str, str],
    background_color_a: Tuple[int, int, int, int] = None,
    true_background_color_b: Tuple[int, int, int, int] = None,
    average_maximum_images_per_page: int = 50,
    current_page: int = 1,
    max_images_size: int = 400,
    bbox_offset: int = 0,
    draw_rectangle_with_color: Tuple[int, int, int] = None,
):
    bboxes_data = [bbox_data for bboxes_data in n_bboxes_data for bbox_data in bboxes_data]
    for idx, bbox_data in enumerate(bboxes_data):
        bbox_data.additional_info['idx'] = idx + 1
    total_bboxes = len(bboxes_data)
    div_children_result = []

    if len(bboxes_data) == 0:
        return html.Div(children=div_children_result)

    div_children_result.append(
        html.Center(
            children=[
                dcc.Markdown(
                    f"Found **{total_bboxes}** bboxes total",
                    style={
                        'font-size': '25px'
                    }
                ),
                html.Hr()
            ]
        ),
    )

    n_split = int(np.ceil(len(bboxes_data) / average_maximum_images_per_page))
    splitted_bboxes_data = np.array_split(bboxes_data, n_split)
    page_bboxes_data = splitted_bboxes_data[current_page-1]

    page_image_paths = np.array([
        bbox_data.image_path for bbox_data in page_bboxes_data
        if bbox_data.image_path is not None
    ])
    unique_image_paths = set(page_image_paths)
    cropped_images_and_renders, labels = [], []
    indexes = []
    for image_path in unique_image_paths:
        indexes_by_image_path = np.where(page_image_paths == image_path)[0]
        bboxes_data_by_image_path = page_bboxes_data[indexes_by_image_path]
        source_image = open_image(image=image_path, open_as_rgb=True)
        cropped_images_and_renders_by_image_path, labels_by_image_path = get_illustrated_bboxes_data(
            source_image=source_image,
            bboxes_data=bboxes_data_by_image_path,
            label_to_base_label_image=label_to_base_label_image,
            background_color_a=background_color_a,
            true_background_color_b=true_background_color_b,
            max_images_size=max_images_size,
            bbox_offset=bbox_offset,
            draw_rectangle_with_color=draw_rectangle_with_color
        )
        indexes.extend(indexes_by_image_path)
        cropped_images_and_renders.extend(cropped_images_and_renders_by_image_path)
        labels.extend(labels_by_image_path)

    inv = np.empty_like(indexes)
    inv[indexes] = np.arange(len(inv), dtype=inv.dtype)
    cropped_images_and_renders = list(np.array(cropped_images_and_renders, dtype=object)[inv])
    labels = list(np.array(labels)[inv])

    for cropped_image_and_render, label, bbox_data in zip(cropped_images_and_renders, labels, page_bboxes_data):
        div_children_result.extend([
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Img(
                                src=f"data:image/png;base64,{get_image_b64(cropped_image_and_render, format='png')}",
                                style={
                                    'max-width': '600px',
                                    'height': '100%'
                                }
                            ),
                        ]
                    ),
                    html.Div(
                        children=[
                            html.Br(),
                            dcc.Markdown(
                                f"Bbox **{bbox_data.additional_info['idx']}/{total_bboxes}**"
                            ),
                            dcc.Markdown(
                                f"**'{label}'**",
                                style={
                                    'font-size': '20px'
                                }
                            ),
                            dcc.Markdown(label_to_description[label]),
                            dcc.Markdown(f"From image '{bbox_data.image_name}'"),
                            dcc.Markdown(f'Bbox: {(bbox_data.xmin, bbox_data.ymin, bbox_data.xmax, bbox_data.ymax)}'),
                        ],
                        style={
                            'border': '3px solid black',
                            'padding': '10px',
                            'max-width': '600px',
                            'margin-left': '30px'
                        }
                    ),
                ],
                style={
                    'display': 'flex',
                    'justify-content': 'start',
                    'margin-top': '10px',
                    'max-width': '1000px'
                }
            ),
            html.Hr()
        ])

    return html.Div(children=div_children_result)
