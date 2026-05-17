import controls
import displayio
import terminalio
import adafruit_display_text.label


group = displayio.Group()
controls.display.root_group = group
label = adafruit_display_text.label.Label(terminalio.FONT, text="PubSubHub v2", color=0xFFFFFF)
label.y = 4
group.append(label)
