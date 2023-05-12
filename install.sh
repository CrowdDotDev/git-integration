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

# Move one directory up from the git-integration folder
cd ~

# Check if git-integration-environment folder exists
if [ ! -d "git-integration-environment" ]; then 
  git clone git@github.com:CrowdDotDev/git-integration-environment.git
else
  # Pull the latest changes from git-integration-environment repository if it exists
  cd git-integration-environment
  git pull origin main
  cd ~
fi

# Move back into the git-integration folder
cd ~/git-integration

# Copy the dotenv-prod file as .env, replacing it if it already exists
cp -f ../git-integration-environment/dotenv-prod .env

echo "The dotenv-prod file has been copied as .env"

echo "Setting up cron job"
# Check if the cron job entry already exists
if ! crontab -l | grep -q "/home/ubuntu/venv/cgit/bin/crowd-git-ingest"; then
    # Save the current crontab into a temporary file
    crontab -l > tmp-cron

    # Append the new cron job entry
    echo "0 * * * * /home/ubuntu/venv/cgit/bin/crowd-git-ingest >> /data/repos/log/cron.log 2>&1" >> tmp-cron

    # Install the new crontab
    crontab tmp-cron

    # Remove the temporary file
    rm tmp-cron

    echo "Cron job added successfully."
else
    echo "Cron job already exists. Nothing to do."
fi
