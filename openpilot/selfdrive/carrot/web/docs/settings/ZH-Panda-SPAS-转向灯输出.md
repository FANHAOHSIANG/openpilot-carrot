<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_OUTPUT" param="CanfdBlinkerKick" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 转向灯输出

**菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKick -->
<a id="CanfdBlinkerKick"></a>

## Panda/SPAS 转向灯输出

`CanfdBlinkerKick`

通过Panda使用车辆SPAS报文发送共用转向灯请求。默认关闭。支持摄像头SCC CAN-FD配置的IONIQ 5 PE、IONIQ 9和Grandeur GN7。 自动点亮使用自动转向灯、手动变道转向灯、手动转弯转向灯及模型观察设置，与USB2CAN和BT2CAN共用启动、保持和结束判断。自动转向灯0关闭自动请求，保留蓝牙按钮的单次请求。 开启在下次OnRoad启动生效，关闭立即生效，需要更新后的Panda固件。开启会停止USB2CAN和BT2CAN输出，等待旧请求到期及独占输出权，并在下次OnRoad关闭CanfdBlinkerControl。 真实拨杆优先并终止自动输出。自动灯光反馈与转向请求隔离。共用请求结束后停止SPAS输出并恢复ECU默认会话，剩余闪烁时间取决于车辆。 保留已有输出和共用设置值。旧模型变道闪烁次数设置已移除，请使用共用设置。 手动变道和转弯正常提前完成时，Panda/SPAS从首次发送请求起至少保持2秒。实际拨杆操作、取消、输入或车道错误会立即结束请求。实际闪烁次数取决于车辆。

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKick -->
<!-- CARROT:AUTO:SOURCE facts="2a53b1e7155f4ac6fdbeb390ab4a6774ebb75147b83a9307d46d9b8a8fc39ced" semantic="e3d01ebf21844e839abfc47d5fc08878416a9261d5535df9497959b72b96c157" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKick -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKick -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKick -->

<!-- CARROT:SETTING:END CanfdBlinkerKick -->
