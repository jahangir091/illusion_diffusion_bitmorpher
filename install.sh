#!/usr/bin/env bash
#################################################
# wget this file inside /home directory
# chmod +x project.sh
# ./project.sh install/start/update
#################################################

project_name="illusion_diffusion"
project_repo="https://github.com/jahangir091/illusion_diffusion.git"

prepare_installation(){
  add-apt-repository ppa:deadsnakes/ppa -y
  apt update -y
  apt upgrade -y
  apt install python3.10-venv -y
  apt install htop -y
  apt install git -y
  apt install nginx -y
  apt install python3-venv libgl1 libglib2.0-0 -y
  git clone "$project_repo"
  cd
  cd /home
  cd "$project_name"
  python3.10 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt

  rm -rf /var/log/"$project_name"
  mkdir /var/log/"$project_name"
  touch /var/log/"$project_name"/access.log
  touch /var/log/"$project_name"/error.log
  chmod 777 -R /var/log/"$project_name"

  rm -rf /etc/systemd/system/"$project_name".service
  cp service.service /etc/systemd/system/"$project_name".service
  systemctl daemon-reload
  systemctl start "$project_name"
  systemctl enable "$project_name"
  systemctl restart "$project_name"

  rm -rf /etc/nginx/sites-available/"$project_name".conf
  rm -rf /etc/nginx/sites-enabled/"$project_name".conf
  cp nginx.conf /etc/nginx/sites-available/"$project_name".conf
  ln -s /etc/nginx/sites-available/"$project_name".conf /etc/nginx/sites-enabled/
  service nginx start
  service "$project_name" restart
  service nginx restart
}

start_rembg(){
  cd
  cd /home/"$project_name"
  service "$project_name" restart
  service nginx restart
}

update_rembg(){
  cd
  cd /home
  git clone "$project_repo"
  cd "$project_name"
  git fetch
  git reset --hard origin/main
}


install="install"
start="start"
update="update"


if [ "$1" == "$start" ]
then
  start_rembg
elif [ "$1" == "$install" ]
then
  prepare_installation
  start_rembg
elif [ "$1" == "$update" ]
then
  update_rembg
else
  printf "\n\n expected flags 'install' or 'start' or 'update'\n\n"
fi
#uvicorn main:app --host 0.0.0.0 --port 8001 --reload
#gunicorn main:app --workers "$1" --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:"$2"
