#!/bin/bash
# This script moves old log files to an archive folder,
# creates a Promtail configuration file,
# downloads and installs the promtail binary,
# and sets up promtail as a systemd service.
#
# Usage:
#   ./setup_promtail.sh -p <LOKI_PASSWORD> -n <HOSTNAME>

usage() {
    echo "Usage: $0 -p <LOKI_PASSWORD> -n <HOSTNAME>"
    exit 1
}

# Parse command line options
while getopts "p:n:" opt; do
  case ${opt} in
    p)
      PASSWORD=${OPTARG}
      ;;
    n)
      HOST=${OPTARG}
      ;;
    *)
      usage
      ;;
  esac
done

# Ensure both variables are provided
if [ -z "${PASSWORD}" ] || [ -z "${HOST}" ]; then
    echo "Error: Both PASSWORD and HOST must be provided."
    usage
fi

# --- Step 1: Move old log files to archive ---
LOG_DIR="/media/pi/SamsungSSD/logs"
ARCHIVE_DIR="/media/pi/SamsungSSD/archive"

if [ -d "$LOG_DIR" ]; then
  echo "Creating archive directory and moving old log files from $LOG_DIR to $ARCHIVE_DIR..."
  mkdir -p "$ARCHIVE_DIR"
  mv "$LOG_DIR"/*.log "$ARCHIVE_DIR"/ 2>/dev/null
else
  echo "Log directory $LOG_DIR does not exist. Skipping file archival."
fi

# --- Step 2: Setup Promtail configuration ---
GRAFANA_DIR=/home/pi/Documents/ulc-malaria-scope/log_config
mkdir -p "$GRAFANA_DIR"

CONFIG_FILE="$GRAFANA_DIR/promtail-config.yaml"
cat << 'EOF' > "$CONFIG_FILE"
server:
  disable: true  # Disables Promtail's internal HTTP server
positions:
  filename: /media/pi/SamsungSSD/positions.yaml  # Stores file tracking state
  sync_period: 10s
clients:
  - url: https://api-grafana.sf.czbiohub.org/loki/push
    basic_auth:
      username: bioe
      password: ${LOKI_PASSWORD}
scrape_configs:
- job_name: remoscope-logs
  static_configs:
  - targets:
      - localhost
    labels:
      app: Remoscope
      host: ${HOSTNAME}
      __path__: /media/pi/SamsungSSD/logs/*.log  # Watches all logs in this directory
  pipeline_stages:
  - match:
      selector: '{app="Remoscope"}'
      stages:
      - multiline:
          firstline: '^\\d{4}-\\d{2}-\\d{2}-\\d{6} .*'
          max_wait_time: 20s
      - labeldrop:
          - filename
      - regex:
          expression: '^\\d{4}-\\d{2}-\\d{2}-\\d{6} - (?P<severity>\\w+) - .*'
      - labels:
          severity:
EOF

echo "Promtail configuration file created at $CONFIG_FILE"

# --- Step 3: Download and install Promtail ---
echo "Downloading promtail..."
wget https://github.com/grafana/loki/releases/download/v3.3.2/promtail-linux-arm.zip -O /tmp/promtail-linux-arm.zip

echo "Unzipping promtail..."
unzip -o /tmp/promtail-linux-arm.zip -d /tmp/

echo "Making promtail executable and moving it to /usr/local/bin..."
chmod +x /tmp/promtail-linux-arm
sudo mv /tmp/promtail-linux-arm /usr/local/bin/promtail

echo "Creating Promtail systemd unit…"

# --- STEP 4: wrapper that exits (and lets systemd retry) --------------------
WRAPPER="/usr/local/bin/promtail-retry.sh"
echo "Creating wrapper script at $WRAPPER…"

sudo tee "$WRAPPER" > /dev/null <<'EOF'
#!/bin/bash
SSD_DIR="/media/pi/SamsungSSD"

# If the drive isn't mounted yet - retry
if ! mountpoint -q "$SSD_DIR"; then
  echo "Promtail: $SSD_DIR not mounted yet, exiting so systemd can retry…" >&2
  exit 1
fi

exec /usr/local/bin/promtail \
     --config.file=/home/pi/Documents/ulc-malaria-scope/log_config/promtail-config.yaml \
     --config.expand-env=true
EOF

sudo chmod +x "$WRAPPER"

# --- STEP 5: promtail-service file setup --------------------

sudo tee /etc/systemd/system/promtail.service > /dev/null <<'EOF'
[Unit]
Description=Promtail (logs on removable SSD)
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/promtail-retry.sh
Restart=always
RestartSec=10
User=pi
Environment="HOSTNAME=HOST_PLACEHOLDER"
Environment="LOKI_PASSWORD=PASSWORD_PLACEHOLDER"
KillMode=mixed
ExecStopPost=/bin/sync

[Install]
WantedBy=multi-user.target
EOF


echo "Updating systemd service file with provided HOST and PASSWORD..."
sudo sed -i "s/Environment=\"HOSTNAME=HOST_PLACEHOLDER\"/Environment=\"HOSTNAME=${HOST}\"/" /etc/systemd/system/promtail.service
sudo sed -i "s/Environment=\"LOKI_PASSWORD=PASSWORD_PLACEHOLDER\"/Environment=\"LOKI_PASSWORD=${PASSWORD}\"/" /etc/systemd/system/promtail.service

echo "Adding LOKI_PASSWORD to as environment variable for interactive sessions..."
sudo sed -i '/^LOKI_PASSWORD=/d' /etc/environment
echo "LOKI_PASSWORD=${PASSWORD}" | sudo tee -a /etc/environment

sed -i '/^export LOKI_PASSWORD=/d' ~/.bashrc
echo "export LOKI_PASSWORD=${PASSWORD}" >> ~/.bashrc
echo "source ~/.bashrc"

echo "Adding permissions to log_config folder"
sudo chmod -R 777 /home/pi/Documents/ulc-malaria-scope/log_config

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "Enabling promtail service..."
sudo systemctl enable promtail.service
echo "Starting promtail service..."

# --- STEP 6: Install udev rule for hard-pull safety --------------------------
echo "Adding udev rule to stop promtail on drive removal…"

sudo tee /etc/udev/rules.d/99-promtail-ssd.rules > /dev/null <<'EOF'
ACTION=="remove", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="SamsungSSD", \
    RUN+="/usr/bin/systemctl stop promtail.service"
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="SamsungSSD", \
    RUN+="/usr/bin/systemctl start promtail.service"
EOF
sudo udevadm control --reload

# Reload udev so the new rule is active immediately
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=block  # optional: re-evaluate current devices

echo "udev rule installed - Promtail will shut down if the SSD is hard-pulled."

sudo systemctl start promtail.service

echo "Promtail setup complete."
