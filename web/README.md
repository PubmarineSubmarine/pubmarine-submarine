https://www.gamingonlinux.com/2022/03/chrome-on-steam-deck-now-supports-the-deck-controller-with-geforce-now-working/

## Set up mission control service (this project)
```
git clone https://github.com/PubmarineSubmarine/pubmarine-submarine.git

sudo tee /etc/systemd/system/missioncontrol.service >/dev/null << EOF
[Unit]
Wants=network.target
[Service]
WorkingDirectory=/home/pi/pubmarine-submarine/web
ExecStart=/home/pi/.local/bin/uv run app/main.py
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now missioncontrol
```


## Set up mediaMTX for raspberry pi cam server
https://github.com/bluenviron/mediamtx?tab=readme-ov-file#linux

```
wget https://github.com/bluenviron/mediamtx/releases/download/v1.13.1/mediamtx_v1.13.1_linux_arm64.tar.gz
tar -xzf mediamtx_v1.13.1_linux_arm64.tar.gz
sudo mv mediamtx /usr/local/bin/
sudo mv mediamtx.yml /usr/local/etc/

sudo tee /etc/systemd/system/mediamtx.service >/dev/null << EOF
[Unit]
Wants=network.target
[Service]
ExecStart=/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
```