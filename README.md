# SteamVR + XSOverlay OSC Bridge (Prototype)

This small Windows helper combines:
- SteamVR Dashboard state (OpenVR events 502/503)
- XSOverlay's `/avatar/parameters/isOverlayOpen` state

It sends the logical OR of both states to VRChat, so the avatar parameter stays
true while either the SteamVR dashboard or an XSOverlay window is open.

## Important: configure XSOverlay to send through the bridge

1. Close XSOverlay.
2. Open XSOverlay's `ExternalMessageAPIConfig.json` in its Config folder.
3. Change its OSC **Send Port** from `9000` to `9002`.
4. Keep its send path as the VRChat OSC avatar-parameter path.
5. Save the file and restart XSOverlay.

The bridge listens on `127.0.0.1:9002` and forwards the other XSOverlay OSC
messages to VRChat at `127.0.0.1:9000`. It intercepts only
`/avatar/parameters/isOverlayOpen` and replaces it with the combined state.

Do not leave XSOverlay sending directly to port 9000, or its value will bypass
the bridge and can overwrite the combined state.

## Install / run

1. Install 64-bit Python 3.11 or newer.
2. Open a terminal in this folder and run:
   `py -3 -m pip install -r requirements.txt`
3. Start SteamVR and VRChat. Enable OSC in VRChat.
4. Double-click `Start-Bridge.bat`.

Keep the bridge running while using VRChat. The console reports state changes.

## SteamVR startup

After testing, create a Windows shortcut to `Start-Bridge.bat` and place it in
`shell:startup`. This starts it at Windows login. SteamVR must be running for
the OpenVR event monitor to connect; if SteamVR starts later, restart the bridge.
A later version can add automatic SteamVR process detection/reconnect.

## Notes / limitations

- This is a source prototype, not a signed installer or native SteamVR driver.
- It uses the OpenVR Python binding's background application interface.
  Python/OpenVR binding compatibility can vary by SteamVR and Python version.
- On startup the bridge assumes XSOverlay is closed until it receives its next
  `isOverlayOpen` OSC update. If XSOverlay is already open before the bridge
  starts, close/reopen an overlay once to refresh the state.
- If your XSOverlay config uses a custom OSC address/path, the bridge needs
  the matching address in `bridge.py`.
- The bridge forwards other single-datagram OSC messages unchanged. OSC bundles
  containing the parameter are not unpacked by this prototype.
- VRChat's default OSC input is UDP 9000. If you changed it, edit `VRCHAT_PORT`.
