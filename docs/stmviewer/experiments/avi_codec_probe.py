"""Local AVI backend probe; generated uint8 images only; no application code changes."""
from pathlib import Path
import json
import sys
import cv2
import numpy as np

out = Path('/tmp/stmviewer-avi-probe')
out.mkdir(exist_ok=True)
print(json.dumps({'python': sys.version, 'opencv': cv2.__version__, 'numpy': np.__version__, 'video_backends': [cv2.videoio_registry.getBackendName(b) for b in cv2.videoio_registry.getBackends()], 'writer_backends': [cv2.videoio_registry.getBackendName(b) for b in cv2.videoio_registry.getWriterBackends()]}))
for line in cv2.getBuildInformation().splitlines():
    if any(s in line for s in ['Video I/O', 'FFMPEG:', 'avcodec:', 'avformat:', 'avutil:', 'swscale:', 'GStreamer:']):
        print(line)
results = []
for codec in ('MJPG', 'FFV1'):
    for width, height, pad in ((64, 48, False), (65, 49, False), (65, 49, True)):
        frames=[]
        yy, xx = np.indices((height, width))
        for n in range(7):
            gray = ((xx * 7 + yy * 3 + n * 19) % 256).astype(np.uint8)
            frame = np.stack([gray, np.roll(gray, n + 1, axis=1), np.roll(gray, n + 2, axis=0)], axis=-1)
            frame[-1, :, :] = [0, 255, 0]
            frame[:, -1, :] = [255, 0, 0]
            if pad:
                frame = np.pad(frame, ((0,height % 2),(0,width % 2),(0,0)), constant_values=0)
            frames.append(frame)
        eh, ew = frames[0].shape[:2]
        fps = 7.5
        path=out / f'{codec}-{width}x{height}-pad{int(pad)}.avi'
        writer=cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (ew, eh), True)
        row={'codec':codec,'source_wh':[width,height],'encoded_wh':[ew,eh],'pad':pad,'requested_fps':fps,'writer_opened':writer.isOpened()}
        if writer.isOpened():
            row['writer_backend']=writer.getBackendName()
            for frame in frames: writer.write(frame)
        writer.release()
        row['bytes']=path.stat().st_size if path.exists() else 0
        cap=cv2.VideoCapture(str(path))
        row['reader_opened']=cap.isOpened()
        if cap.isOpened():
            row['reader_backend']=cap.getBackendName()
            row['read_fps']=cap.get(cv2.CAP_PROP_FPS)
            row['reported_count']=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        decoded=[]
        while True:
            ok, frame=cap.read()
            if not ok: break
            decoded.append(frame)
        cap.release()
        row['decoded_count']=len(decoded)
        row['decoded_shapes']=sorted(set(tuple(f.shape) for f in decoded))
        if decoded:
            shapes_match=all(a.shape==b.shape for a,b in zip(frames,decoded))
            row['shapes_match']=shapes_match
            errors=[]
            for expected, actual in zip(frames,decoded):
                dh,dw=actual.shape[:2]
                errors.append(np.abs(expected[:dh,:dw].astype(np.int16)-actual.astype(np.int16)))
            row['max_absolute_error_on_returned_region']=int(max(x.max() for x in errors))
            row['mean_absolute_error_on_returned_region']=float(np.mean([x.mean() for x in errors]))
            row['all_expected_pixels_exact']=bool(len(decoded)==len(frames) and shapes_match and all(np.array_equal(a,b) for a,b in zip(frames,decoded)))
        results.append(row)
        print(json.dumps(row))
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
