import os, io, uuid, boto3, base64, time
from fastapi import FastAPI, HTTPException, Form
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import asyncio
import json

app = FastAPI(title="Fractal Generation Service")

# Initialize AWS clients
ssm = boto3.client('ssm', region_name='ap-southeast-2')

def get_parameter(name):
    try:
        response = ssm.get_parameter(Name=name)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"❌ Error getting parameter {name}: {e}")
        fallback_values = {
            '/fractal-app/region': 'ap-southeast-2',
            '/fractal-app/s3-bucket': 'n11608676-asses2',
            '/fractal-app/dynamodb-table': 'n11608676-FractalsTable'
        }
        return fallback_values.get(name, '')

# Get configuration
try:
    REGION = get_parameter('/fractal-app/region')
    S3_BUCKET = get_parameter('/fractal-app/s3-bucket')
    DYNAMO_TABLE = get_parameter('/fractal-app/dynamodb-table')
    print(f"✅ Fractal Service: Loaded configuration - Bucket={S3_BUCKET}, Table={DYNAMO_TABLE}")
except Exception as e:
    print(f"⚠️ Fractal Service: Using fallback configuration: {e}")
    REGION = "ap-southeast-2"
    S3_BUCKET = "n11608676-asses2"
    DYNAMO_TABLE = "n11608676-FractalsTable"

# Initialize AWS clients
try:
    s3 = boto3.client("s3", region_name=REGION)
    dynamo = boto3.resource("dynamodb", region_name=REGION).Table(DYNAMO_TABLE)
    AWS_AVAILABLE = True
    print("✅ Fractal Service: AWS services initialized successfully")
except Exception as e:
    print(f"⚠️ Fractal Service: Running without AWS: {e}")
    s3, dynamo = None, None
    AWS_AVAILABLE = False

# Import fractal generation functions from your existing code
def create_color_map(base_color):
    color_maps = {
        'blue': ['#00008B', '#1E90FF', '#87CEEB', '#B0E0E6'],
        'red': ['#8B0000', '#FF4500', '#FF6347', '#FFA07A'],
        'green': ['#006400', '#32CD32', '#90EE90', '#98FB98'],
        'purple': ['#4B0082', '#8A2BE2', '#9370DB', '#DDA0DD'],
        'orange': ['#FF8C00', '#FFA500', '#FFB6C1', '#FFDAB9'],
        'darkblue': ['#000080', '#0000CD', '#4169E1', '#6495ED'],
        'black': ['#000000', '#2F4F4F', '#696969', '#A9A9A9']
    }
    colors = color_maps.get(base_color, color_maps['blue'])
    return LinearSegmentedColormap.from_list('custom', colors)

def generate_tree_fractal(depth, color, ax):
    def draw_tree(x, y, length, angle, depth_left):
        if depth_left == 0:
            return
            
        x_end = x + length * np.cos(angle)
        y_end = y + length * np.sin(angle)
        
        line_width = max(0.5, depth_left * 1.5)
        alpha = 0.3 + 0.7 * (depth_left / depth)
        
        ax.plot([x, x_end], [y, y_end], color=color, linewidth=line_width, alpha=alpha)
        
        new_length = length * (0.6 + 0.1 * np.random.random())
        angle_variation = np.pi/6 * (0.8 + 0.4 * np.random.random())
        
        if depth_left > 1:
            draw_tree(x_end, y_end, new_length, angle + angle_variation, depth_left - 1)
            draw_tree(x_end, y_end, new_length, angle - angle_variation, depth_left - 1)
            
            if depth_left > 3:
                draw_tree(x_end, y_end, new_length * 0.7, angle + angle_variation * 1.5, depth_left - 2)
                draw_tree(x_end, y_end, new_length * 0.7, angle - angle_variation * 1.5, depth_left - 2)
    
    draw_tree(0, -2, 1.5, np.pi/2, depth)
    ax.set_aspect('equal')
    ax.set_xlim(-4, 4)
    ax.set_ylim(-2, 6)

def generate_koch_snowflake(depth, color, ax):
    def koch_curve(start, end, depth):
        if depth == 0:
            return [start, end]
        
        diff = end - start
        p1 = start + diff / 3
        p3 = start + 2 * diff / 3
        
        angle = np.pi / 3
        rot = np.array([[np.cos(angle), -np.sin(angle)], 
                       [np.sin(angle), np.cos(angle)]])
        p2 = p1 + rot @ (diff / 3)
        
        return (koch_curve(start, p1, depth-1) + 
                koch_curve(p1, p2, depth-1) + 
                koch_curve(p2, p3, depth-1) + 
                koch_curve(p3, end, depth-1))
    
    size = 2
    points = [
        np.array([0, size * np.sqrt(3)/3]),
        np.array([-size/2, -size * np.sqrt(3)/6]),
        np.array([size/2, -size * np.sqrt(3)/6])
    ]
    
    all_points = []
    for i in range(3):
        curve = koch_curve(points[i], points[(i+1)%3], depth)
        all_points.extend(curve)
    
    points_array = np.array(all_points)
    ax.plot(points_array[:, 0], points_array[:, 1], color=color, linewidth=2)
    ax.set_aspect('equal')
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)

def generate_sierpinski_triangle(depth, color, ax):
    def sierpinski(vertices, depth):
        if depth == 0:
            tri = plt.Polygon(vertices, color=color, alpha=0.7)
            ax.add_patch(tri)
        else:
            midpoints = [
                (vertices[0] + vertices[1]) / 2,
                (vertices[1] + vertices[2]) / 2,
                (vertices[2] + vertices[0]) / 2
            ]
            
            sierpinski([vertices[0], midpoints[0], midpoints[2]], depth-1)
            sierpinski([vertices[1], midpoints[0], midpoints[1]], depth-1)
            sierpinski([vertices[2], midpoints[1], midpoints[2]], depth-1)
    
    vertices = np.array([[0, 2], [-2, -2], [2, -2]])
    sierpinski(vertices, depth)
    ax.set_aspect('equal')
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-2.5, 2.5)

def generate_dragon_curve(depth, color, ax):
    def dragon_curve(start, end, depth, direction=1):
        if depth == 0:
            return [start, end]
        
        diff = end - start
        perpendicular = np.array([-diff[1], diff[0]]) * direction
        mid = (start + end) / 2 + perpendicular / 2
        
        return (dragon_curve(start, mid, depth-1, 1) +
                dragon_curve(mid, end, depth-1, -1))
    
    start = np.array([-2, 0])
    end = np.array([2, 0])
    points = dragon_curve(start, end, depth)
    
    points_array = np.array(points)
    ax.plot(points_array[:, 0], points_array[:, 1], color=color, linewidth=1.5)
    ax.set_aspect('equal')
    ax.set_xlim(-3, 3)
    ax.set_ylim(-2, 2)

def generate_fern_fractal(depth, color, ax):
    transformations = [
        (0.0, 0.0, 0.0, 0.16, 0.0, 0.0, 0.01),
        (0.85, 0.04, -0.04, 0.85, 0.0, 1.6, 0.85),
        (0.2, -0.26, 0.23, 0.22, 0.0, 1.6, 0.07),
        (-0.15, 0.28, 0.26, 0.24, 0.0, 0.44, 0.07)
    ]
    
    x, y = 0, 0
    points_x, points_y = [], []
    
    for _ in range(min(5000, 1000 * depth)):
        r = np.random.random()
        a, b, c, d, e, f, prob = transformations[0]
        cumulative_prob = 0
        
        for transform in transformations:
            cumulative_prob += transform[6]
            if r <= cumulative_prob:
                a, b, c, d, e, f, _ = transform
                break
        
        x, y = a*x + b*y + e, c*x + d*y + f
        points_x.append(x)
        points_y.append(y)
    
    ax.scatter(points_x, points_y, color=color, s=0.5, alpha=0.6)
    ax.set_aspect('equal')
    ax.set_xlim(-3, 3)
    ax.set_ylim(0, 10)

def generate_circle_packing(depth, color, ax):
    def pack_circles(center_x, center_y, radius, depth_left):
        if depth_left == 0 or radius < 0.1:
            return
            
        circle = plt.Circle((center_x, center_y), radius, fill=False, 
                           color=color, linewidth=1, alpha=0.7)
        ax.add_patch(circle)
        
        if depth_left > 1:
            smaller_radius = radius / 2.5
            angles = [0, 2*np.pi/3, 4*np.pi/3]
            for angle in angles:
                new_x = center_x + (radius - smaller_radius) * np.cos(angle)
                new_y = center_y + (radius - smaller_radius) * np.sin(angle)
                pack_circles(new_x, new_y, smaller_radius, depth_left - 1)
    
    pack_circles(0, 0, 2, depth)
    ax.set_aspect('equal')
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)

@app.post("/generate")
async def generate_fractal(
    depth: int = Form(..., ge=1, le=8),
    color: str = Form("blue"),
    fractal_type: str = Form("tree"),
    username: str = Form(...)
):
    print(f"🎨 Fractal Service: Generating {fractal_type} fractal for {username}")
    
    # Validate inputs
    valid_colors = ["blue", "red", "green", "purple", "orange", "darkblue", "black"]
    if color not in valid_colors:
        color = "blue"
    
    valid_types = ["tree", "snowflake", "sierpinski", "dragon", "fern", "circles"]
    if fractal_type not in valid_types:
        fractal_type = "tree"

    try:
        # Create figure with high quality
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 10), dpi=120)
        ax.set_axis_off()
        fig.patch.set_facecolor('black')
        ax.set_facecolor('black')

        # Generate selected fractal type
        fractal_names = {
            "tree": "Recursive Tree",
            "snowflake": "Koch Snowflake", 
            "sierpinski": "Sierpinski Triangle",
            "dragon": "Dragon Curve",
            "fern": "Barnsley Fern",
            "circles": "Circle Packing"
        }
        
        fractal_name = fractal_names.get(fractal_type, "Recursive Tree")
        
        if fractal_type == "tree":
            generate_tree_fractal(depth, color, ax)
        elif fractal_type == "snowflake":
            generate_koch_snowflake(min(depth, 6), color, ax)
        elif fractal_type == "sierpinski":
            generate_sierpinski_triangle(min(depth, 7), color, ax)
        elif fractal_type == "dragon":
            generate_dragon_curve(min(depth, 15), color, ax)
        elif fractal_type == "fern":
            generate_fern_fractal(depth, color, ax)
        elif fractal_type == "circles":
            generate_circle_packing(min(depth, 6), color, ax)
        
        ax.set_title(f'{fractal_name} (Depth: {depth})', color='white', pad=20, fontsize=14)
        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.1, 
                   facecolor='black', dpi=120)
        buf.seek(0)
        plt.close(fig)

        fractal_id = str(uuid.uuid4())
        
        if AWS_AVAILABLE:
            # Save to S3
            s3_key = f"fractals/{username}/{fractal_id}.png"
            s3.upload_fileobj(buf, S3_BUCKET, s3_key, ExtraArgs={"ContentType": "image/png"})
            
            # Generate pre-signed URL
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': S3_BUCKET, 'Key': s3_key},
                ExpiresIn=3600
            )
            
            # Save to DynamoDB
            dynamo.put_item(Item={
                "Username": username,
                "FractalId": fractal_id,
                "Depth": depth,
                "Color": color,
                "FractalType": fractal_name,
                "S3Key": s3_key,
                "CreatedAt": str(int(time.time()))
            })
            
            return {
                "message": f"{fractal_name} generated and saved to cloud!",
                "id": fractal_id,
                "depth": depth,
                "color": color,
                "fractal_type": fractal_name,
                "saved_to_cloud": True,
                "image_url": presigned_url
            }
        else:
            # Fallback: return image data directly
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            return {
                "message": f"{fractal_name} generated (AWS not available)!",
                "id": fractal_id,
                "depth": depth,
                "color": color,
                "fractal_type": fractal_name,
                "saved_to_cloud": False,
                "image_data": f"data:image/png;base64,{image_base64}"
            }

    except Exception as e:
        raise HTTPException(500, f"Error generating fractal: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "fractal_generation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)