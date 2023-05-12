sudo apt update
sudo apt upgrade
sudo apt install python3-pip
sudo apt install python-is-python3
sudo apt install python3.10-venv
sudo mkdir /data
sudo chown ubuntu /data
mkdir -p /data/repos/log
mkdir -p ~/venv/cgit && python -m venv ~/venv/cgit
source ~/venv/cgit/bin/activate
pip install --upgrade pip
cd ~/git-integration ; pip install -e .

