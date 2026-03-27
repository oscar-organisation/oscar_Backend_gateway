


$env:LIVEKIT_KEYS="oscar_prod_key:oscar_super_secret_prod_key"; $env:DEFAULT_ROOM_NAME="oscar-lot1-room"; python services/token-generator/generate.py



execute gen token in server 

docker run --rm -e LIVEKIT_KEYS='oscar_prod_key:oscar_super_secret_prod_key' -e DEFAULT_ROOM_NAME='oscar-lot1-room' -v /home/ubuntu/oscar_Backend_gateway/services/token-generator:/tokengen livekit-media-simulator python3 /tokengen/generate.py



execute gen token in my pc for Prod

ssh oscar-vps "docker run --rm -e LIVEKIT_KEYS='oscar_prod_key:oscar_super_secret_prod_key' -e DEFAULT_ROOM_NAME='oscar-lot1-room' -v /home/ubuntu/oscar_Backend_gateway/services/token-generator:/tokengen livekit-media-simulator python3 /tokengen/generate.py 2>&1"