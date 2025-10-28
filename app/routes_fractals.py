import os, uuid, boto3, json
from fastapi import APIRouter, Request, HTTPException, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from auth import verify_jwt_token
import requests

router = APIRouter()

# SQS Configuration
sqs = boto3.client('sqs', region_name='ap-southeast-2')
FRACTAL_SERVICE_URL = "n11608676-autoscale-assesment3-785201285.ap-southeast-2.elb.amazonaws.com"  # Will be replaced with ALB URL
SQS_QUEUE_URL = None  # Will be set after queue creation

# Initialize SQS queue
def init_sqs_queue():
    global SQS_QUEUE_URL
    try:
        # Create SQS queue for fractal generation requests
        response = sqs.create_queue(
            QueueName='fractal-generation-queue',
            Attributes={
                'VisibilityTimeout': '300',  # 5 minutes
                'MessageRetentionPeriod': '86400'  # 1 day
            }
        )
        SQS_QUEUE_URL = response['QueueUrl']
        print(f"✅ SQS queue created: {SQS_QUEUE_URL}")
    except Exception as e:
        print(f"⚠️ Using existing SQS queue: {e}")
        # Queue might already exist, try to get URL
        try:
            response = sqs.get_queue_url(QueueName='fractal-generation-queue')
            SQS_QUEUE_URL = response['QueueUrl']
        except Exception as e2:
            print(f"❌ Could not get SQS queue: {e2}")
            SQS_QUEUE_URL = None

# Initialize on startup
init_sqs_queue()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_HTML = os.path.join(BASE_DIR, "templates", "dashboard.html")

@router.get("/dashboard")
def dashboard(request: Request):
    # ... (keep your existing dashboard code)
    token = request.query_params.get("token")
    if not token:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
    
    username = "user"
    if token:
        try:
            payload = verify_jwt_token(token)
            username = payload.get("cognito:username", "user")
        except HTTPException:
            return RedirectResponse(url="/")
    
    if not os.path.exists(DASHBOARD_HTML):
        return HTMLResponse(f"""
        <html>
            <head><title>Fractal Dashboard</title></head>
            <body>
                <div class="container">
                    <h1>Fractal Dashboard</h1>
                    <p>Welcome, {username}!</p>
                    <a href="/">Back to Login</a>
                </div>
            </body>
        </html>
        """)
    
    try:
        with open(DASHBOARD_HTML, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{username}}", username)
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h3>Error loading dashboard: {str(e)}</h3>", status_code=500)

# Background task to process SQS messages
async def process_fractal_messages():
    if not SQS_QUEUE_URL:
        return
    
    try:
        # Receive messages from SQS
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20
        )
        
        messages = response.get('Messages', [])
        for message in messages:
            try:
                # Parse message body
                body = json.loads(message['Body'])
                
                # Call fractal service
                fractal_response = requests.post(
                    f"{FRACTAL_SERVICE_URL}/generate",
                    data=body
                )
                
                if fractal_response.status_code == 200:
                    # Success - delete message from queue
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    print(f"✅ Processed fractal generation for {body.get('username')}")
                else:
                    print(f"❌ Failed to generate fractal: {fractal_response.text}")
                    
            except Exception as e:
                print(f"❌ Error processing message: {e}")
                
    except Exception as e:
        print(f"❌ Error receiving SQS messages: {e}")

@router.post("/fractals/generate")
async def generate_fractal(
    background_tasks: BackgroundTasks,
    request: Request,
    depth: int = Form(..., ge=1, le=8),
    color: str = Form("blue"),
    fractal_type: str = Form("tree")
):
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing/invalid Authorization header")
    token = auth.split(" ", 1)[1]
    payload = verify_jwt_token(token)
    username = payload.get("cognito:username", "user")

    # Validate inputs
    valid_colors = ["blue", "red", "green", "purple", "orange", "darkblue", "black"]
    if color not in valid_colors:
        color = "blue"
    
    valid_types = ["tree", "snowflake", "sierpinski", "dragon", "fern", "circles"]
    if fractal_type not in valid_types:
        fractal_type = "tree"

    # Add background task to process messages
    background_tasks.add_task(process_fractal_messages)

    if SQS_QUEUE_URL:
        # Send message to SQS for async processing
        message_body = {
            "depth": depth,
            "color": color,
            "fractal_type": fractal_type,
            "username": username
        }
        
        try:
            response = sqs.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(message_body),
                MessageGroupId='fractal-generation'
            )
            
            return {
                "message": f"Fractal generation queued successfully!",
                "queue_position": response.get('MessageId'),
                "status": "queued"
            }
            
        except Exception as e:
            print(f"❌ Error sending to SQS: {e}")
            # Fallback to direct call
            pass

    # Fallback: Direct call to fractal service
    try:
        fractal_response = requests.post(
            f"{FRACTAL_SERVICE_URL}/generate",
            data={
                "depth": depth,
                "color": color,
                "fractal_type": fractal_type,
                "username": username
            }
        )
        
        if fractal_response.status_code == 200:
            return fractal_response.json()
        else:
            raise HTTPException(500, f"Fractal service error: {fractal_response.text}")
            
    except Exception as e:
        raise HTTPException(500, f"Error generating fractal: {str(e)}")

@router.get("/fractals/list")
def list_fractals(request: Request):
    # ... (keep your existing list_fractals code)
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing/invalid Authorization header")
    token = auth.split(" ", 1)[1]
    payload = verify_jwt_token(token)
    username = payload.get("cognito:username", "user")

    try:
        # Query DynamoDB for user's fractals
        dynamo = boto3.resource('dynamodb', region_name='ap-southeast-2').Table('n11608676-FractalsTable')
        s3 = boto3.client('s3', region_name='ap-southeast-2')
        
        resp = dynamo.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("Username").eq(username),
            ScanIndexForward=False
        )
        items = resp.get("Items", [])
        
        for item in items:
            try:
                url = s3.generate_presigned_url(
                    "get_object", 
                    Params={"Bucket": "n11608676-asses2", "Key": item["S3Key"]}, 
                    ExpiresIn=3600
                )
                item["ImageURL"] = url
            except Exception as e:
                print(f"Error generating URL for {item['S3Key']}: {e}")
                item["ImageURL"] = ""
        
        return items
        
    except Exception as e:
        print(f"Error listing fractals: {e}")
        raise HTTPException(500, f"Error listing fractals: {str(e)}")