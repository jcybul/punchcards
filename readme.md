
## to build he image
docker build --platform linux/amd64 --no-cache -t gcr.io/punchcards/punchcard-api:latest .
## to push the image 
docker push gcr.io/punchcards/punchcard-api:latest

gcloud run deploy punchcard-api-staging \
  --image=gcr.io/punchcards/punchcard-api-staging:latest \
  --region=us-central1 \
  --platform=managed \
  --project=punchcards


## staging commands  
docker build --platform linux/amd64 --no-cache -t gcr.io/punchcards/punchcard-api-staging:latest .

docker push gcr.io/punchcards/punchcard-api-staging:latest