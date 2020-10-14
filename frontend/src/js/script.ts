import Webcam from './webcam';
import { Document } from './interfaces';

const webcamElement = document.querySelector('.video') as HTMLVideoElement;
const canvasElement = document.querySelector('.canvas') as HTMLCanvasElement;
const imageElement = document.querySelector('.photo') as HTMLImageElement;
const inputFps = document.querySelector('.input-field--fps input') as HTMLInputElement;
const inputQuality = document.querySelector('.input-field--quality input') as HTMLInputElement;
const inputDelay = document.querySelector('.input-field--delay input') as HTMLInputElement;
const buttonFlipCamera = document.querySelector('.button--camera-flip') as HTMLButtonElement;
const buttonStart = document.querySelector('.button--start') as HTMLButtonElement;
const buttonFullScreen = document.querySelector('.button--fullscreen') as HTMLButtonElement;
const buttonDownload = document.querySelector('.button--download') as HTMLButtonElement;

const webcam = new Webcam(webcamElement, 'environment', canvasElement);

const MAX_FPS = 60;
const DEFAULT_FPS = 5;
const MAX_QUALITY = 1;
const DEFAULT_QUALITY = 0.92;
const DEFAULT_DELAY = 200;
const SECOND = 1000;

let fps = localStorage.getItem('fps') || DEFAULT_FPS;
let quality = localStorage.getItem('quality') || DEFAULT_QUALITY;
let delay = localStorage.getItem('delay') || DEFAULT_DELAY;
let fpsTimoutId;
let isStreaming = false;

(async () => {
  await webcam.start();

  buttonFlipCamera.disabled = webcam.webcamCount === 1;
  buttonDownload.disabled = true;

  inputFps.value = `${fps}`;
  inputQuality.value = `${quality}`;
  inputDelay.value = `${delay}`;

  const startStream = async () => {
    buttonStart.textContent = 'Pause';
    buttonDownload.disabled = false;
    isStreaming = true;

    await webcam.realtimeStart(+fps, +delay);

    const snap = () => {
      if (!isStreaming) {
        return;
      }

      fpsTimoutId = setTimeout(async () => {
        try {
          imageElement.src = await webcam.snap({ quality: Number(quality) });
          snap();
        } catch (err) {
          snap();
        }
      }, SECOND / (Number(fps) || DEFAULT_FPS));
    };

    snap();
  };

  const stopStream = async () => {
    await webcam.realtimeEnd();
    isStreaming = false;
    clearTimeout(fpsTimoutId);
    fpsTimoutId = null;
    buttonStart.textContent = 'Start';
    buttonDownload.disabled = true;
  };

  const handleButtonStartClick = () => {
    if (fpsTimoutId) {
      stopStream();
    } else {
      startStream();
    }
  };

  const handleButtonFlipCameraClick = () => webcam.flip();

  const activateFullscreen = (element) => {
    if (element.requestFullscreen) {
      element.requestFullscreen();
    } else if (element.mozRequestFullScreen) {
      element.mozRequestFullScreen();
    } else if (element.webkitRequestFullscreen) {
      element.webkitRequestFullscreen();
    } else if (element.msRequestFullscreen) {
      element.msRequestFullscreen();
    }
  };

  const deactivateFullscreen = () => {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if ((document as Document).mozCancelFullScreen) {
      (document as Document).mozCancelFullScreen();
    } else if ((document as Document).webkitExitFullscreen) {
      (document as Document).webkitExitFullscreen();
    }
  };

  const handleButtonFullscreenClick = () => {
    const fullscreenElement = document.fullscreenElement
      || (document as Document).mozFullScreenElement
      || (document as Document).webkitFullscreenElement;

    if (fullscreenElement) {
      deactivateFullscreen();
    } else {
      activateFullscreen(imageElement);
    }
  };

  const handleButtonDownloadClick = async () => {
    const link = document.createElement('a');
    link.download = 'filename.png';
    link.href = await webcam.snap({ quality: Number(quality) });
    link.click();
  };

  const handleInputFPSChange = (evt) => {
    const input = evt.target as HTMLInputElement;

    if (Number(input.value) > MAX_FPS) {
      input.value = `${MAX_FPS}`;
    }

    localStorage.setItem('fps', input.value);
    fps = Number(input.value);

    if (fpsTimoutId) {
      clearTimeout(fpsTimoutId);
      startStream();
    }
  };

  const handleInputDelayChange = (evt) => {
    const input = evt.target as HTMLInputElement;

    localStorage.setItem('delay', input.value);
    delay = Number(input.value);

    if (fpsTimoutId) {
      clearTimeout(fpsTimoutId);
      startStream();
    }
  };

  const handleInputQualityChange = (evt) => {
    const input = evt.target as HTMLInputElement;

    if (Number(input.value) > MAX_QUALITY) {
      input.value = `${MAX_QUALITY}`;
    }

    localStorage.setItem('quality', input.value);
    quality = Number(input.value);
  };

  buttonStart.addEventListener('click', handleButtonStartClick);
  buttonFlipCamera.addEventListener('click', handleButtonFlipCameraClick);
  buttonFullScreen.addEventListener('click', handleButtonFullscreenClick);
  buttonDownload.addEventListener('click', handleButtonDownloadClick);
  inputFps.addEventListener('input', handleInputFPSChange);
  inputQuality.addEventListener('input', handleInputQualityChange);
  inputDelay.addEventListener('input', handleInputDelayChange);
})();