import {Config} from '@remotion/cli/config';

// 1080x1920 @ 30 fps, H.264 High, yuv420p, CRF 18 (see STEP 8 of the brief).
// PNG frames -> true limited-range yuv420p (JPEG frames made FFmpeg emit full-range yuvj420p).
Config.setVideoImageFormat('png');
Config.setColorSpace('bt709');
Config.setCodec('h264');
Config.setCrf(18);
Config.setPixelFormat('yuv420p');
Config.setOverwriteOutput(true);
Config.setConcurrency(4);
// The cloud container ships a Playwright headless shell; on Windows remove this line
// (Remotion downloads its own Chrome Headless Shell automatically).
if (process.platform === 'linux') {
  Config.setBrowserExecutable('/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell');
}
