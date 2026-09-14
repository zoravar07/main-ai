const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, screen } = require('electron');
const path = require('path');

let panel = null;
let tray = null;

const WIDTH = 1080;
const HEIGHT = 700;

function createPanel() {
  panel = new BrowserWindow({
    width: WIDTH,
    height: HEIGHT,
    show: false,
    frame: true,
    resizable: true,
    minWidth: 900,
    minHeight: 600,
    transparent: false,
    vibrancy: 'under-window',
    visualEffectState: 'active',
    alwaysOnTop: false,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });

  panel.loadFile('workspace.html');

  // card clicks open real apps in the default browser
  panel.webContents.setWindowOpenHandler(function (d) {
    require('electron').shell.openExternal(d.url);
    return { action: 'deny' };
  });

  // Clicking away hides the panel, the way a menu bar utility should behave.
  
}

function positionPanel() {
  const cursor = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursor);
  const { x, y, width } = display.workArea;

  // Sit under the menu bar, horizontally near the tray icon.
  const px = Math.round(Math.min(Math.max(cursor.x - WIDTH / 2, x + 8), x + width - WIDTH - 8));
  panel.setPosition(px, y + 8, false);
}

function togglePanel() {
  if (!panel) return;
  if (panel.isVisible()) {
    panel.hide();
    return;
  }
  positionPanel();
  panel.show();
  panel.focus();
  panel.webContents.send('focus-input');
}

app.whenReady().then(() => {
  // No dock icon — this lives in the menu bar.
  

  createPanel();

  const icon = nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setTitle('Z');
  tray.setTitle('Z');
  tray.setToolTip('Zopro');
  tray.on('click', togglePanel);

  // Right-click for a quit option, the way a menu bar app should behave.
  tray.on('right-click', () => {
    tray.popUpContextMenu(Menu.buildFromTemplate([
      { label: 'Open Zopro', accelerator: 'CommandOrControl+Shift+Z', click: togglePanel },
      { type: 'separator' },
      { label: 'Quit Zopro', accelerator: 'Command+Q', click: () => app.quit() },
    ]));
  });

  globalShortcut.register('CommandOrControl+Shift+Z', togglePanel);
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', (e) => {
  e.preventDefault();
});
