from typing import List, Tuple

import pandas as pd
import numpy as np

from two_stage_pipeliner.metrics_counters.core.detection import get_df_all_bboxes_matchings


def get_df_all_bboxes(
    n_true_bboxes: List[List[Tuple[int, int, int, int]]],
    n_true_labels: List[List[str]],
    n_pred_bboxes: List[List[Tuple[int, int, int, int]]],
    n_pred_labels: List[List[str]],
    minimum_iou: float,
    extra_bbox_label: str = ""
) -> pd.DataFrame:
    n_true_bboxes = [
        [tuple(bbox) for bbox in sublist]
        for sublist in n_true_bboxes
    ]
    n_pred_bboxes = [
        [tuple(bbox) for bbox in sublist]
        for sublist in n_pred_bboxes
    ]

    df_bboxes_all = get_df_all_bboxes_matchings(
        n_true_bboxes,
        n_pred_bboxes,
        minimum_iou
    )
    for idx in df_bboxes_all.index:
        img_idx = df_bboxes_all.loc[idx, 'indexes']
        is_true_bbox = df_bboxes_all.loc[idx, 'is_true_bbox']
        found = df_bboxes_all.loc[idx, 'found']

        if is_true_bbox:
            true_bbox = df_bboxes_all.loc[idx, 'true_bbox']
            img_bbox_idx = n_true_bboxes[img_idx].index(
                tuple(true_bbox)
            )
            df_bboxes_all.loc[
                idx, 'true_label'
            ] = n_true_labels[img_idx][img_bbox_idx]
        else:
            df_bboxes_all.loc[
                idx, 'true_label'
            ] = f"{extra_bbox_label} (extra bbox)"

        if found:
            pred_bbox = df_bboxes_all.loc[idx, 'pred_bbox']
            img_bbox_idx = n_pred_bboxes[img_idx].index(
                tuple(pred_bbox)
            )
            df_bboxes_all.loc[
                idx, 'pred_label'
            ] = n_pred_labels[img_idx][img_bbox_idx]

    return df_bboxes_all


def get_df_TP(df_bboxes_all: pd.DataFrame,
              extra_bbox_label: str,
              soft: bool = False,
              known_class_names: List[str] = None,
              by_class_name: str = None) -> pd.DataFrame:
    if soft:
        query = (
            '(found and is_true_bbox and true_label in @known_class_names and true_label == pred_label)'

            ' or '

            '(found and is_true_bbox and not (true_label in @known_class_names))'
        )
        if extra_bbox_label in known_class_names:  # this line doesn't work in query code
            query = (
                f'{query}'
                ' or '
                '(found and not is_true_bbox and pred_label == @extra_bbox_label)'
            )
        else:
            query = (
                f'{query}'
                ' or '
                '(found and not is_true_bbox)'
            )
        df_TP = df_bboxes_all.query(query)
    else:
        df_TP = df_bboxes_all.query(
            '(found and is_true_bbox and true_label == pred_label)'

            ' or '

            f'(found and not is_true_bbox and pred_label == @extra_bbox_label)'
        )
    if by_class_name:
        df_TP = df_TP.query(
            f'true_label == "{by_class_name}"'
        )
    return df_TP


def get_df_FP(df_bboxes_all: pd.DataFrame,
              extra_bbox_label: str,
              soft: bool = False,
              known_class_names: List[str] = None,
              by_class_name: str = None) -> pd.DataFrame:
    if soft:
        query = (
            '(found and is_true_bbox and true_label in @known_class_names and true_label != pred_label)'
        )
        if extra_bbox_label in known_class_names:  # this line doesn't work in query code
            query = (
                f'{query}'
                ' or '
                '(found and not is_true_bbox and pred_label != @extra_bbox_label)'
            )
        df_FP = df_bboxes_all.query(query)
    else:
        df_FP = df_bboxes_all.query(
            'found and is_true_bbox and true_label != pred_label'

            ' or '

            f'found and not is_true_bbox and pred_label != @extra_bbox_label'
        )

    if by_class_name:
        df_FP = df_FP.query(
            f'true_label == "{by_class_name}" or pred_label == "{by_class_name}"'
        )
    return df_FP


def get_df_FN(df_bboxes_all: pd.DataFrame,
              by_class_name: str = None) -> pd.DataFrame:
    df_FN = df_bboxes_all.query('is_true_bbox and not found')
    if by_class_name:
        df_FN = df_FN.query(
            f'true_label == "{by_class_name}"'
        )
    return df_FN


def get_df_pipeline_matching_for_one_item(df_image: pd.DataFrame) -> pd.DataFrame:
    TP = np.sum(df_image['error_type'] == 'TP')
    FP = np.sum(df_image['error_type'] == 'FP')
    FN = np.sum(df_image['error_type'] == 'FN')
    items = []
    for idx in df_image.index:
        if df_image.loc[idx, 'true_bbox'] is not None:
            items.append({
                'true_bbox': df_image.loc[idx, 'true_bbox'],
                'found': df_image.loc[idx, 'found'],
                'pred_bbox': df_image.loc[idx, 'pred_bbox'],
                'iou': df_image.loc[idx, 'iou'],
                'error_type': df_image.loc[idx, 'error_type']
            })
    true_bboxes_num = np.sum([1 for x in df_image['true_bbox'] if x is not None])
    pred_bboxes_num = np.sum([1 for x in df_image['pred_bbox'] if x is not None])
    df_matchings = pd.DataFrame({
        'items': [items],
        'TP': [TP],
        'FP': [FP],
        'FN': [FN],
        'true_bboxes_num': [true_bboxes_num],
        'pred_bboxes_num': [pred_bboxes_num]
    })
    return df_matchings


def get_df_pipeline_matchings(
    n_true_bboxes: List[List[Tuple[int, int, int, int]]],
    n_true_labels: List[List[str]],
    n_pred_bboxes: List[List[Tuple[int, int, int, int]]],
    n_pred_labels: List[List[str]],
    minimum_iou: float,
    soft: bool = False,
    known_class_names: List[str] = None,
    extra_bbox_label: str = "",
):
    df_bboxes_all = get_df_all_bboxes(
        n_true_bboxes,
        n_true_labels,
        n_pred_bboxes,
        n_pred_labels,
        minimum_iou,
        extra_bbox_label
    )
    df_TP = get_df_TP(df_bboxes_all, extra_bbox_label, soft, known_class_names)
    df_FP = get_df_FP(df_bboxes_all, extra_bbox_label, soft, known_class_names)
    df_FN = get_df_FN(df_bboxes_all)
    for tag, df in [('TP', df_TP),
                    ('FP', df_FP),
                    ('FN', df_FN)]:
        for idx in df.index:
            df_bboxes_all.loc[idx, 'error_type'] = tag

    image_idx_to_df_idxs = {
        image_idx: []
        for image_idx in df_bboxes_all['indexes']
    }
    for idx in df_bboxes_all.index:
        image_idx_to_df_idxs[df_bboxes_all.loc[idx, 'indexes']].append(idx)

    pipeline_matchings = []
    for image_idx in image_idx_to_df_idxs:
        df_image = df_bboxes_all.loc[image_idx_to_df_idxs[image_idx]]
        pipeline_matchings.append(get_df_pipeline_matching_for_one_item(df_image))

    df_pipeline_matchings = pd.concat(pipeline_matchings,
                                      ignore_index=True)

    return df_pipeline_matchings


def get_df_pipeline_metrics(
    n_true_bboxes: List[List[Tuple[int, int, int, int]]],
    n_true_labels: List[List[str]],
    n_pred_bboxes: List[List[Tuple[int, int, int, int]]],
    n_pred_labels: List[List[str]],
    minimum_iou: float,
    soft: bool = False,
    known_class_names: List[str] = None,
    extra_bbox_label: str = "",
) -> pd.DataFrame:
    df_bboxes_all = get_df_all_bboxes(
        n_true_bboxes,
        n_true_labels,
        n_pred_bboxes,
        n_pred_labels,
        minimum_iou,
        extra_bbox_label
    )
    class_names = np.unique(
        [x for sublist in n_true_labels for x in sublist]
        +
        [x for sublist in n_pred_labels for x in sublist]
    )

    metrics = []
    for class_name in list(class_names) + [
        f"{extra_bbox_label} (extra bbox)"
    ]:
        support = len(df_bboxes_all.query(f'true_label == "{class_name}"'))
        df_TP = get_df_TP(df_bboxes_all, extra_bbox_label, soft, known_class_names, class_name)
        df_FP = get_df_FP(df_bboxes_all, extra_bbox_label, soft, known_class_names, class_name)
        df_FN = get_df_FN(df_bboxes_all, class_name)
        TP, FP, FN = len(df_TP), len(df_FP), len(df_FN)
        if support > 0:
            precision = TP / (TP + FP + 1e-6)
            recall = TP / (TP + FN + 1e-6)
            if precision > 0 and recall > 0:
                fscore = 2 / (1 / precision + 1 / recall)
            else:
                fscore = 0
        else:
            precision = 0
            recall = 0
            fscore = 0

        metrics.append({
            'class_name': class_name,
            'support': support,
            'TP': TP,
            'FP': FP,
            'FN': FN,
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'fscore': round(fscore, 3)
        })
    df_metrics = pd.DataFrame(metrics)
    df_metrics = df_metrics[
        ['class_name', 'support', 'TP', 'FP',
         'FN', 'precision', 'recall', 'fscore']
    ]
    df_metrics = df_metrics.query('support > 0')

    df_metrics_nonFPdetector = df_metrics[
        df_metrics['class_name'] != f"{extra_bbox_label} (extra bbox)"
    ]
    weighted_average_precision = np.average(
        df_metrics_nonFPdetector['precision'],
        weights=df_metrics_nonFPdetector['support']
    )
    weighted_average_recall = np.average(
        df_metrics_nonFPdetector['recall'],
        weights=df_metrics_nonFPdetector['support']
    )
    weighted_average_fscore = np.average(
        df_metrics_nonFPdetector['fscore'],
        weights=df_metrics_nonFPdetector['support']
    )
    macro_average_precision = np.average(
        df_metrics_nonFPdetector['precision']
    )
    macro_average_recall = np.average(
        df_metrics_nonFPdetector['recall']
    )
    macro_average_fscore = np.average(
        df_metrics_nonFPdetector['fscore']
    )

    if known_class_names and soft:
        df_metrics_nonFPdetector_known = df_metrics_nonFPdetector[
            df_metrics_nonFPdetector['class_name'].isin(known_class_names)
        ]
        weighted_average_precision_known = np.average(
            df_metrics_nonFPdetector_known['precision'],
            weights=df_metrics_nonFPdetector_known['support']
        )
        weighted_average_recall_known = np.average(
            df_metrics_nonFPdetector_known['recall'],
            weights=df_metrics_nonFPdetector_known['support']
        )
        weighted_average_fscore_known = np.average(
            df_metrics_nonFPdetector_known['fscore'],
            weights=df_metrics_nonFPdetector_known['support']
        )
        macro_average_precision_known = np.average(
            df_metrics_nonFPdetector_known['precision']
        )
        macro_average_recall_known = np.average(
            df_metrics_nonFPdetector_known['recall']
        )
        macro_average_fscore_known = np.average(
            df_metrics_nonFPdetector_known['fscore']
        )

    weighted_metrics = {
        'class_name': 'weighted avg',
        'support': np.sum(df_metrics_nonFPdetector['support']),
        'TP': np.sum(df_metrics_nonFPdetector['TP']),
        'FP': np.sum(df_metrics_nonFPdetector['FP']),
        'FN': np.sum(df_metrics_nonFPdetector['FN']),
        'precision': round(weighted_average_precision, 3),
        'recall': round(weighted_average_recall, 3),
        'fscore': round(weighted_average_fscore, 3)
    }
    macro_metrics = {
        'class_name': 'macro avg',
        'support': np.sum(df_metrics_nonFPdetector['support']),
        'TP': np.sum(df_metrics_nonFPdetector['TP']),
        'FP': np.sum(df_metrics_nonFPdetector['FP']),
        'FN': np.sum(df_metrics_nonFPdetector['FN']),
        'precision': round(macro_average_precision, 3),
        'recall': round(macro_average_recall, 3),
        'fscore': round(macro_average_fscore, 3)
    }
    if known_class_names and soft:
        weighted_metrics_known = {
            'class_name': 'known weighted avg',
            'support': np.sum(df_metrics_nonFPdetector_known['support']),
            'TP': np.sum(df_metrics_nonFPdetector_known['TP']),
            'FP': np.sum(df_metrics_nonFPdetector_known['FP']),
            'FN': np.sum(df_metrics_nonFPdetector_known['FN']),
            'precision': round(weighted_average_precision_known, 3),
            'recall': round(weighted_average_recall_known, 3),
            'fscore': round(weighted_average_fscore_known, 3)
        }
        macro_metrics_known = {
            'class_name': 'known macro avg',
            'support': np.sum(df_metrics_nonFPdetector_known['support']),
            'TP': np.sum(df_metrics_nonFPdetector_known['TP']),
            'FP': np.sum(df_metrics_nonFPdetector_known['FP']),
            'FN': np.sum(df_metrics_nonFPdetector_known['FN']),
            'precision': round(macro_average_precision_known, 3),
            'recall': round(macro_average_recall_known, 3),
            'fscore': round(macro_average_fscore_known, 3)
        }
        df_metrics = df_metrics.append(
            [weighted_metrics, macro_metrics,
             weighted_metrics_known, macro_metrics_known]
        ).reset_index(drop=True)
    else:
        df_metrics = df_metrics.append(
            [weighted_metrics, macro_metrics]
        ).reset_index(drop=True)

    df_metrics.sort_values(by='support', ascending=False, inplace=True)
    df_metrics.reset_index(drop=True, inplace=True)
    df_metrics.set_index('class_name', inplace=True)
    return df_metrics
