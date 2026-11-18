<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_OUTPUT" param="CanfdBlinkerKick" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS Indicator Output

**Menu:** Vehicle & Hardware \> Indicator Control \> Output Device

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKick -->
<a id="CanfdBlinkerKick"></a>

## Panda/SPAS Indicator Output

`CanfdBlinkerKick`

Sends common indicator requests through Panda using vehicle SPAS messages. Default off. Supported on camera-SCC CAN-FD with ECAN SPAS 0x165 (24 bytes), 0x16A (32 bytes) and stalk 0x3C1 (8 bytes), without a model-name restriction. Automatic indication follows Automatic turn signals, Manual Lane-change Indicator, Manual Turn Indicator and model observation settings. Start, hold and completion use the same policy as USB2CAN and BT2CAN. Auto Blinker 0 disables automatic requests and retains explicit Bluetooth indicator buttons as single taps in D. Enabling applies on the next onroad start; disabling applies immediately. Updated Panda firmware is required. Enabling suspends USB2CAN/BT2CAN output and waits for outstanding external commands and exclusive ownership. CanfdBlinkerControl is disabled on the next onroad start. Physical lever operation ends automatic output. Automatic lamp feedback is isolated from steering requests, with verified physical lever input taking priority. Ending the common request stops SPAS output and restores the ECU default session. Residual lamp flashing depends on the vehicle. Existing saved output and common indication values are retained. The former model-only flash-count setting is retired. Select indication behavior through the common settings. For manual lane changes and turns, normal completion waits for a minimum of two seconds from the first Panda/SPAS transmission request. Physical lever input, cancellation and input or lane errors end the request immediately. Actual flash count depends on the vehicle. Before a new request, requires ten CRC-valid advancing stock SPAS frames and a fresh neutral stalk. Stalk reception remains required while the ECU is temporarily silenced. Matching CAN IDs alone does not establish compatibility.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKick -->
<!-- CARROT:AUTO:SOURCE facts="ee226426b3de8a4b1c3cb9b6826ecf6c9dff8d8f55f37510882e0069b0ea39c8" semantic="4258b15380b0ddee8b6c5ee745b8d2c5e8af4aff0cae1bcbea9b5ae26b087c43" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> Indicator Control \> Output Device
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKick -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKick -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKick -->

<!-- CARROT:SETTING:END CanfdBlinkerKick -->
