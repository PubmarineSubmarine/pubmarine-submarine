import controls
import displayio
import terminalio
import adafruit_display_text.label


group = displayio.Group()
controls.display.root_group = group
label = adafruit_display_text.label.Label(terminalio.FONT, text="PubSubHub v2", color=0xFFFFFF)
label.y = 4
group.append(label)
label_1 = adafruit_display_text.label.Label(terminalio.FONT, text="PubSubHub v2", color=0xFFFFFF)
label_1.y = 14
group.append(label_1)
label_2 = adafruit_display_text.label.Label(terminalio.FONT, text="PubSubHub v2", color=0xFFFFFF)
label_2.y = 24
group.append(label_2)
controls.display.refresh()
