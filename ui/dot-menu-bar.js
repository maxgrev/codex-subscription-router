;(() => {
  const fs = require("node:fs");
  const electron = require("electron");
  const LOG = "/tmp/codex-mux-dot.log";
  const DOT_ROUTE = "/dots/home?window=dot";
  const PANEL_WIDTH = 420;
  const PANEL_HEIGHT = 640;
  const AUTOSAVE_NAME = "CodexMuxYourDot";
  const NS_MIN_Y_EDGE = 1;
  const POPOVER_TRANSIENT = 1;
  const MOUSE_UP_EVENTS = 12;
  const AUTORESIZE_FILL = 18;

  let objc = null;
  let appKit = null;
  let foundation = null;
  let ns = null;
  let target = null;
  let statusItem = null;
  let popover = null;
  let panel = null;
  let panelRequest = null;
  let panelWindow = null;
  let attached = false;
  let rendering = false;

  function log(message) {
    try {
      fs.appendFileSync(LOG, new Date().toISOString() + " " + message + "\n");
    } catch (error) {
      console.error("codex-mux: Your dot log:", error);
    }
  }

  function describeError(error) {
    return error && error.stack ? error.stack : String(error);
  }

  async function waitForWindowManager() {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const manager = global.codexMuxWindowManager;
      if ((manager?.getPrimaryWindows?.().length ?? 0) > 0) return manager;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error("the main window never became ready");
  }

  async function createPanel() {
    const manager = await waitForWindowManager();
    const created = await manager.createWindow({
      title: "Your dot",
      width: PANEL_WIDTH,
      height: PANEL_HEIGHT,
      appearance: "detached",
      show: false,
      initialRoute: DOT_ROUTE,
      lockTitle: true,
      onCreated: (window) => {
        global.codexMuxDotWebContentsId = window.webContents.id;
      },
    });
    if (created == null || created.isDestroyed()) {
      throw new Error("createWindow returned nothing");
    }
    created.excludedFromShownWindowsMenu = true;
    created.once("closed", () => {
      panel = null;
      panelWindow = null;
      attached = false;
      rendering = false;
    });
    panel = created;
    return created;
  }

  function ensurePanel() {
    if (panel != null && !panel.isDestroyed()) return Promise.resolve(panel);
    panelRequest =
      panelRequest ??
      createPanel().finally(() => {
        panelRequest = null;
      });
    return panelRequest;
  }

  function alignPanelWindow() {
    if (!rendering || panelWindow == null) return;
    const host = popover.contentViewController().view();
    const frame = host
      .window()
      .convertRectToScreen$(host.convertRect$toView$(host.bounds(), null));
    panelWindow.setFrame$display$(frame, false);
  }

  // The popover follows its status item when the menu bar moves it, for
  // example to another display, without telling the delegate again.
  function followPopoverWindow() {
    const center = foundation.NSNotificationCenter.defaultCenter();
    center.removeObserver$(target);
    center.addObserver$selector$name$object$(
      target,
      selector("popoverWindowDidMove:"),
      ns("NSWindowDidMoveNotification"),
      popover.contentViewController().view().window(),
    );
  }

  // Chromium only draws while the Electron window is ordered in, even after its
  // content view moves into the popover. Keep that window invisible, click-through,
  // and on the popover's display while the popover is open.
  function setRendering(browserWindow, active) {
    if (browserWindow == null || browserWindow.isDestroyed()) return;
    if (active === rendering) return;
    rendering = active;
    if (!active) {
      browserWindow.hide();
      return;
    }
    alignPanelWindow();
    browserWindow.showInactive();
  }

  function attachPanel(browserWindow) {
    if (attached) return;
    const content = objc.fromPointer(browserWindow.getNativeWindowHandle());
    panelWindow = content.window();
    browserWindow.setOpacity(0);
    browserWindow.setIgnoreMouseEvents(true);
    browserWindow.setFocusable(false);
    const host = popover.contentViewController().view();
    const stale = host.subviews();
    for (let index = stale.count() - 1; index >= 0; index -= 1) {
      stale.objectAtIndex$(index).removeFromSuperview();
    }
    host.addSubview$(content);
    content.setFrame$(host.bounds());
    content.setAutoresizingMask$(AUTORESIZE_FILL);
    attached = true;
  }

  function makePopover(button) {
    const controller = appKit.NSViewController.alloc().init();
    controller.setView$(
      appKit.NSView.alloc().initWithFrame$({
        origin: { x: 0, y: 0 },
        size: { width: PANEL_WIDTH, height: PANEL_HEIGHT },
      }),
    );
    const delegate = objc.NobjcProtocol.implement("NSPopoverDelegate", {
      popoverDidShow$: () => {
        followPopoverWindow();
        alignPanelWindow();
      },
      popoverDidClose$: () => {
        button.highlight$(false);
        setRendering(panel, false);
      },
    });
    global.codexMuxDotPopoverDelegate = delegate;
    const created = appKit.NSPopover.alloc().init();
    created.setBehavior$(POPOVER_TRANSIENT);
    created.setAnimates$(true);
    created.setDelegate$(delegate);
    created.setContentSize$({ width: PANEL_WIDTH, height: PANEL_HEIGHT });
    created.setContentViewController$(controller);
    return created;
  }

  async function togglePopover(button) {
    if (popover != null && popover.isShown()) {
      popover.performClose$(null);
      button.highlight$(false);
      return;
    }
    popover = popover ?? makePopover(button);
    button.highlight$(true);
    popover.showRelativeToRect$ofView$preferredEdge$(
      button.bounds(),
      button,
      NS_MIN_Y_EDGE,
    );
    const browserWindow = await ensurePanel();
    if (!popover.isShown()) return;
    attachPanel(browserWindow);
    setRendering(browserWindow, true);
  }

  function selector(name) {
    return objc.callFunction(
      "NSSelectorFromString",
      { returns: ":", args: ["@"] },
      ns(name),
    );
  }

  function makeTarget() {
    const Target = objc.NobjcClass.define({
      name: "CodexMuxDotTarget",
      superclass: "NSObject",
      methods: {
        "togglePopover:": {
          types: "v@:@",
          implementation: (_self, sender) => {
            togglePopover(sender).catch((error) => {
              log("toggle failed " + describeError(error));
            });
          },
        },
        "popoverWindowDidMove:": {
          types: "v@:@",
          implementation: () => alignPanelWindow(),
        },
      },
    });
    const created = Target.alloc().init();
    global.codexMuxDotTarget = created;
    return created;
  }

  function installClickTarget(button) {
    button.setTarget$(target);
    button.setAction$(selector("togglePopover:"));
    button.sendActionOn$(MOUSE_UP_EVENTS);
  }

  function setupMenuBar() {
    const image = appKit.NSImage.imageWithSystemSymbolName$accessibilityDescription$(
      ns("circle.fill"),
      ns("Your dot"),
    );
    if (image == null) throw new Error("menu bar icon is missing");
    image.setTemplate$(true);

    statusItem = appKit.NSStatusBar.systemStatusBar().statusItemWithLength$(-2);
    global.codexMuxDotStatusItem = statusItem;
    statusItem.setAutosaveName$(ns(AUTOSAVE_NAME));
    const button = statusItem.button();
    if (button == null) throw new Error("status item has no button");
    button.setImage$(image);
    button.setToolTip$(ns("Your dot"));
    button.setAccessibilityLabel$(ns("Your dot"));
    target = makeTarget();
    installClickTarget(button);
    log("menu bar item ready");

    ensurePanel().catch((error) => log("prewarm failed " + describeError(error)));
  }

  electron.app.whenReady().then(async () => {
    try {
      objc = await import("objc-js");
      appKit = new objc.NobjcLibrary(
        "/System/Library/Frameworks/AppKit.framework/AppKit",
      );
      foundation = new objc.NobjcLibrary(
        "/System/Library/Frameworks/Foundation.framework/Foundation",
      );
      ns = (value) => foundation.NSString.stringWithUTF8String$(value);
      setupMenuBar();
    } catch (error) {
      log("setup failed " + describeError(error));
    }
  });
})();
