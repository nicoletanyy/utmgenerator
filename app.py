from flask import Flask, render_template, request, jsonify, redirect
from flask_cors import CORS
from datetime import datetime
import shortuuid
from database import Database

app = Flask(__name__)
CORS(app)

# ============================================
# YOUR SUPABASE CONNECTION STRING
# Replace with your actual Supabase connection string
# ============================================
SUPABASE_URL = "postgresql://postgres.xwnbwiufgmkqepcjeafa:UjOTsghFHw78sKpz@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# Initialize database
db = Database(SUPABASE_URL)

def generate_utm_url(url, params):
    """Build UTM URL from parameters"""
    utm_parts = []
    
    if params.get('utm_source'):
        utm_parts.append(f"utm_source={params['utm_source']}")
    if params.get('utm_medium'):
        utm_parts.append(f"utm_medium={params['utm_medium']}")
    if params.get('utm_campaign'):
        utm_parts.append(f"utm_campaign={params['utm_campaign']}")
    if params.get('utm_term'):
        utm_parts.append(f"utm_term={params['utm_term']}")
    if params.get('utm_content'):
        utm_parts.append(f"utm_content={params['utm_content']}")
    
    if not utm_parts:
        return url
    
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}{'&'.join(utm_parts)}"

@app.route('/')
def index():
    """Serve the frontend"""
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate_link():
    """Generate a new UTM link and store in database"""
    try:
        data = request.json
        
        full_url = generate_utm_url(data.get('url', ''), data)
        link_id = shortuuid.ShortUUID().random(length=10)
        short_code = shortuuid.ShortUUID().random(length=6).upper()  # Uppercase for consistency
        
        print(f"📝 Generated short_code: '{short_code}'")
        
        utm_params = {
            'utm_source': data.get('utm_source', ''),
            'utm_medium': data.get('utm_medium', ''),
            'utm_campaign': data.get('utm_campaign', ''),
            'utm_term': data.get('utm_term', ''),
            'utm_content': data.get('utm_content', '')
        }
        
        # Store in database
        db.create_link(link_id, short_code, full_url, utm_params)
        
        base_url = request.host_url.rstrip('/')
        
        return jsonify({
            'success': True,
            'id': link_id,
            'full_url': full_url,
            'short_url': f"{base_url}/go/{short_code}",
            'short_code': short_code
        })
    except Exception as e:
        print(f"❌ Error in generate_link: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/go/<short_code>')
def track_and_redirect(short_code):
    """Track click and redirect to original URL"""
    try:
        print(f"🔍 Looking for short_code: '{short_code}'")
        
        # Make search case-insensitive by converting to uppercase
        short_code_upper = short_code.upper()
        print(f"🔍 Searching for uppercase: '{short_code_upper}'")
        
        link = db.get_link_by_code(short_code_upper)
        
        if not link:
            print(f"❌ Link not found for code: '{short_code}'")
            return "Link not found", 404
        
        print(f"✅ Link found! Redirecting to: {link['full_url'][:100]}...")
        
        # Record the click with country tracking
        db.record_click(
            link['id'],
            request.remote_addr,
            request.headers.get('User-Agent', 'Unknown')
        )
        
        # Redirect to original URL
        return redirect(link['full_url'])
    except Exception as e:
        print(f"❌ Error in track_and_redirect: {e}")
        import traceback
        traceback.print_exc()
        return "Error processing request", 500

@app.route('/api/stats/<link_id>')
def get_stats(link_id):
    """Get click statistics for a link"""
    try:
        link = db.get_link_by_id(link_id)
        
        if not link:
            return jsonify({'error': 'Link not found'}), 404
        
        stats = db.get_click_stats(link_id)
        
        return jsonify({
            'link': link,
            'stats': stats
        })
    except Exception as e:
        print(f"❌ Error in get_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/links')
def get_all_links():
    """Get all generated links"""
    try:
        links = db.get_all_links()
        base_url = request.host_url.rstrip('/')
        
        # Add short_url to each link
        for link in links:
            if link.get('short_code'):
                link['short_url'] = f"{base_url}/go/{link['short_code']}"
        
        return jsonify(links)
    except Exception as e:
        print(f"❌ Error in get_all_links: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/links/<link_id>', methods=['DELETE'])
def delete_link(link_id):
    """Delete a link and all its clicks"""
    try:
        result = db.delete_link(link_id)
        if result:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Link not found'}), 404
    except Exception as e:
        print(f"❌ Error in delete_link: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_total_stats():
    """Get overall statistics"""
    try:
        stats = db.get_total_stats()
        return jsonify(stats)
    except Exception as e:
        print(f"❌ Error in get_total_stats: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 UTM Tracker with Short URL & Country Tracking")
    print("📍 Open http://localhost:3000 in your browser")
    print("=" * 50)
    app.run(debug=True, port=3000)