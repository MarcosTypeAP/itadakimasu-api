# Itadakimasu API
The API for the [I.T.A.D.A.K.I.M.A.S.U. mobile app](https://github.com/MarcosTypeAP/itadakimasu-client).

This service provides endpoints for searching and downloading YouTube videos in MP3 format.
It also adds metadata to the files, and you can search for this metadata through a Spotify API wrapper.

# Install
```shell
# Download the repo
$ git clone https://github.com/MarcosTypeAP/itadakimasu-api.git
$ cd itadakimasu-api

# Create an environment file.
# Possible variables can be found in `./src/settings.py`.
$ cat << EOF > .env
SPOTIFY_API_SEARCH_URL=https://api.spotify.com/v1/search
SPOTIFY_API_TOKEN_URL=https://accounts.spotify.com/api/token
EOF

# To use the Spotify API, you need to create a Spotify App and save its credentials in a file.
# To learn how to create an app, visit https://developer.spotify.com/documentation/web-api
$ cat << EOF > .secrets
SPOTIFY_API_CLIENT_ID=<your-client-id>
SPOTIFY_API_CLIENT_SECRET=<your-client-secret>
EOF
```

You also need to have `docker` and optionally `docker-compose` installed.

# Usage
```shell
# With `docker-compose`
$ docker-compose up

# Without `docker-compose`
$ docker volume create itadakimasu-api-logs
$ docker build --tag itadakimasu-api .
# Because `docker run` doesn't support secrets, you need to pass them as environment variables.
$ cat .secrets >> .env
$ docker run --rm -it \
    --env-file=.env \
    --mount type=bind,src="$(pwd)",dst=/app \
    --mount type=volume,src=itadakimasu-api-logs,dst=/var/log/app \
    -p 4000:4000 \
    itadakimasu-api
```
