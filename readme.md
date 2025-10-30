
## to build he image
docker build --platform linux/amd64 --no-cache -t gcr.io/punchcards/punchcard-api:latest .
## to push the image 
docker push gcr.io/punchcards/punchcard-api:latest