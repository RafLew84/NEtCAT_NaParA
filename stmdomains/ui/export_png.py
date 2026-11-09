"""Render the existing image scene into a labelled PNG on the GUI thread."""

from collections.abc import Mapping
import json
from typing import Any

from PyQt6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from stmdomains.core.export import ExportOptions
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.result_style import LegendEntry, describe_result


def render_export_png(frame: PresentedFrame, view: Mapping[str, Any], options: ExportOptions, *,
                      context: Mapping[str, Any] | None = None) -> bytes:
    app = QApplication.instance()
    if app is None:
        raise ValueError('Eksport PNG wymaga uruchomionego interfejsu Qt.')
    image_view = ImageView()
    image_view.set_frame(frame)
    mode, layers = view.get('assignment_mode', 'domains'), view.get('layers', {})
    image_view.set_barriers_visible(layers.get('barriers', False))
    image_view.set_assignment_mode(mode)
    image_view.set_layers(centers=layers.get('centers', True), boxes=layers.get('boxes', False),
                          masks=layers.get('masks', False), opacity=layers.get('mask_opacity', 45) / 100)
    image_view.set_domain_layers(fill=layers.get('fill', True), outlines=layers.get('outlines', True),
                                 numbers=layers.get('numbers', True), opacity=layers.get('domain_opacity', 35) / 100)
    scene = image_view.scene()
    if scene is None:
        raise ValueError('Brak sceny do eksportu.')
    source = image_view.sceneRect()
    if options.crop is not None:
        source = source.intersected(QRectF(*options.crop))
    if source.isEmpty():
        raise ValueError('Wycinek leży poza obrazem.')
    description = describe_result(frame.result, mode)
    legend = description.legend
    if frame.result is None:
        legend = (LegendEntry('Oznaczenia wejściowe', '#46e6be', len(frame.annotations.detections)),)
    if layers.get('barriers') and frame.result is not None and frame.result.barrier_mask is not None:
        legend = (*legend, LegendEntry('Bariery [px]', '#ff8e2e', int(frame.result.barrier_mask.sum())))
    result = frame.result
    analysis_id = (result.metadata.get('series_analysis', {}).get('run_id') or result.metadata.get('analysis_id', '')) if result else ''
    catalogue_id = result.metadata.get('model_id', '') if result else ''
    context = context or {}
    analysis_id = context.get('analysis_id', analysis_id)
    catalogue_id = context.get('catalogue_id', catalogue_id)
    analysis_status = context.get('analysis_status', result.status if result else 'unanalysed')
    crop_label = 'wycinek' if options.crop else 'pełny obraz'
    view_label = 'wyrównany' if frame.mode == 'expanded_aligned' else 'oryginalny'
    mode_label = {'domains': 'Domeny', 'classes': 'Klasy', 'input': 'Wejściowe'}[mode]
    caption = (f'Klatka {frame.frame.working_index+1} · źródłowa {frame.frame.source_index+1} · {mode_label}\n'
               f'{view_label} · {crop_label} · gamma {frame.gamma:g} · skala w px\n{description.summary}')
    variant = context.get('result_variant', 'automatic')
    label = {'after_corrections': 'Po korektach', 'automatic': 'Bazowy automat', 'input': 'Oznaczenia wejściowe'}[variant]
    state = {'corrected': 'korekty ręczne', 'manual_only': 'tylko ręczne — brak automatu',
             'automatic': 'bez korekt', 'unanalysed': 'brak analizy'}.get(context.get('frame_state', ''), '')
    caption += f'\n{label} · {state}'
    if result is None and analysis_status != 'unanalysed':
        state_label = {'not_in_analysis': 'Klatka poza wybranym przebiegiem', 'not_run': 'Analiza niewykonana',
                       'error': 'Błąd analizy', 'unavailable': 'Wynik niedostępny'}.get(analysis_status, analysis_status)
        caption += '\n' + state_label
    if not frame.rendered.has_data:
        caption += '\nBrak skończonych próbek obrazu.'
    notes = (f'Zakres widoku [x, y, szer., wys.] px: {source.x():g}, {source.y():g}, {source.width():g}, {source.height():g}.\n'
             'Legenda i liczniki dotyczą całej klatki. Obszary domen są przybliżone.\n'
             + ('Poza obramowaniem pola: padding, bez pomiaru.\n' if frame.mode == 'expanded_aligned' else '')
             + f'Analiza: {str(analysis_id)[:12] or "brak"} · katalog: {str(catalogue_id)[:12] or "brak"}.\n'
             + frame.annotations.detection_message + '\n' + frame.registration_text)
    font = QFont(QApplication.font())
    font.setPixelSize(14)
    metrics = QFontMetrics(font)
    width = options.image_width
    flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft)
    def text_height(text: str) -> int:
        return metrics.boundingRect(0, 0, width, 100000, flags, text).height() + 8
    caption_height, notes_height = text_height(caption), text_height(notes)
    legend_rows: list[list[LegendEntry]] = [[]]
    used = 0
    for entry in legend:
        item_width = min(width, metrics.horizontalAdvance(f'{entry.label}: {entry.count}') + 36)
        if used + item_width > width and legend_rows[-1]:
            legend_rows.append([])
            used = 0
        legend_rows[-1].append(entry)
        used += item_width
    image_height = max(1, round(width * source.height() / source.width()))
    row_heights = [max((metrics.boundingRect(0, 0, width - 18, 100000, flags,
                    f'{e.label}: {e.count}').height() for e in row), default=metrics.height()) + 8
                   for row in legend_rows]
    legend_height = sum(row_heights)
    total_height = caption_height + image_height + legend_height + notes_height + 48
    if (width + 32) * total_height > 64_000_000:
        raise ValueError('Eksportowany PNG jest zbyt duży. Wybierz szerszy wycinek lub mniejszą szerokość PNG.')
    output = QImage(width + 32, total_height, QImage.Format.Format_ARGB32)
    if output.isNull():
        raise ValueError('Brak pamięci na obraz PNG.')
    output.fill(QColor('#101820'))
    painter = QPainter(output)
    painter.setFont(font)
    painter.setPen(QColor('white'))
    painter.drawText(QRectF(16, 12, width, caption_height), flags, caption)
    image_rect = QRectF(16, caption_height + 16, width, image_height)
    # Item painters replace their local clipping rectangle. A separate device
    # bounds the scene physically, so cropped overlays cannot cover the caption.
    body = QImage(width, image_height, QImage.Format.Format_ARGB32)
    if body.isNull():
        painter.end()
        raise ValueError('Brak pamięci na wycinek PNG.')
    body.fill(QColor(Qt.GlobalColor.darkGray))
    scene_painter = QPainter(body)
    scene_painter.setFont(font)
    scene.render(scene_painter, QRectF(0, 0, width, image_height), source, Qt.AspectRatioMode.IgnoreAspectRatio)
    scene_painter.end()
    painter.drawImage(image_rect.topLeft(), body)
    painter.resetTransform()
    painter.setFont(font)
    y = int(image_rect.bottom()) + 10
    for row, row_height in zip(legend_rows, row_heights):
        x = 16
        for entry in row:
            painter.fillRect(QRectF(x, y + 3, 12, 12), QColor(entry.color))
            painter.setPen(QColor('white'))
            label = f'{entry.label}: {entry.count}'
            painter.drawText(QRectF(x + 18, y, min(width - 18, metrics.horizontalAdvance(label) + 2), row_height), flags, label)
            x += min(width, metrics.horizontalAdvance(label) + 36)
        y += row_height
    painter.setPen(QColor('#b6c7d2'))
    painter.drawText(QRectF(16, y, width, notes_height), flags, notes)
    painter.end()
    output.setText('STM Domains', json.dumps({'format': 'stmdomains-png', 'version': 1,
        **context, 'analysis_id': analysis_id, 'catalogue_id': catalogue_id, 'working_index': frame.frame.working_index,
        'source_index': frame.frame.source_index, 'mode': frame.mode, 'assignment_mode': mode,
        'analysis_status': analysis_status, 'gamma': frame.gamma,
        'normalization': 'raw-frame percentiles 2–98', 'crop_view_px': list(source.getRect()),
        'image_rect_px': list(image_rect.getRect()), 'caption': caption,
        'legend': [{'label': entry.label, 'color': entry.color, 'count': entry.count} for entry in legend]}, ensure_ascii=False))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not output.save(buffer, 'PNG'):
        raise OSError('Nie można zapisać obrazu PNG.')
    return buffer.data().data()
