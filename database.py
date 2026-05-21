import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests

class Database:
    def __init__(self, database_url):
        """Initialize connection to Supabase"""
        print("🔄 Connecting to Supabase...")
        self.database_url = database_url
        self.create_tables()
    
    def create_tables(self):
        """Create tables if they don't exist"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()
            
            # Create UTM links table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS utm_links (
                    id TEXT PRIMARY KEY,
                    short_code TEXT UNIQUE,
                    full_url TEXT NOT NULL,
                    utm_source TEXT,
                    utm_medium TEXT,
                    utm_campaign TEXT,
                    utm_term TEXT,
                    utm_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_clicks INTEGER DEFAULT 0
                )
            """)
            
            # Create clicks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clicks (
                    id SERIAL PRIMARY KEY,
                    link_id TEXT REFERENCES utm_links(id),
                    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    country TEXT
                )
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_short_code ON utm_links(short_code)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_clicks_link_id ON clicks(link_id)")
            
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Supabase tables ready")
        except Exception as e:
            print(f"⚠️ Table creation error: {e}")
    
    def get_country_from_ip(self, ip_address):
        """Get country from IP address"""
        if ip_address in ['127.0.0.1', 'localhost', '::1']:
            return 'Local'
        
        try:
            response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=5)
            data = response.json()
            if data.get('status') == 'success':
                return data.get('country', 'Unknown')
            return 'Unknown'
        except Exception as e:
            return 'Unknown'
    
    def create_link(self, link_id, short_code, full_url, utm_params):
        """Store a new UTM link"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO utm_links 
                (id, short_code, full_url, utm_source, utm_medium, utm_campaign, utm_term, utm_content, total_clicks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
            """, (
                link_id, short_code, full_url,
                utm_params.get('utm_source', ''),
                utm_params.get('utm_medium', ''),
                utm_params.get('utm_campaign', ''),
                utm_params.get('utm_term', ''),
                utm_params.get('utm_content', '')
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Link created: {short_code}")
            return True
        except Exception as e:
            print(f"❌ Error creating link: {e}")
            return False
    
    def get_link_by_code(self, short_code):
        """Find a link by its short code"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT * FROM utm_links WHERE short_code = %s", (short_code,))
            result = cur.fetchone()
            
            cur.close()
            conn.close()
            
            if result:
                return dict(result)
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_link_by_id(self, link_id):
        """Find a link by its ID"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT * FROM utm_links WHERE id = %s", (link_id,))
            result = cur.fetchone()
            
            cur.close()
            conn.close()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def record_click(self, link_id, ip_address, user_agent):
        """Record a click"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()
            
            country = self.get_country_from_ip(ip_address)
            
            cur.execute("""
                INSERT INTO clicks (link_id, ip_address, user_agent, country)
                VALUES (%s, %s, %s, %s)
            """, (link_id, ip_address, user_agent[:500], country))
            
            cur.execute("""
                UPDATE utm_links SET total_clicks = total_clicks + 1 WHERE id = %s
            """, (link_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Click recorded - Country: {country}")
            return True
        except Exception as e:
            print(f"❌ Error recording click: {e}")
            return False
    
    def get_all_links(self):
        """Get all links"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT * FROM utm_links ORDER BY created_at DESC")
            results = cur.fetchall()
            
            cur.close()
            conn.close()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def get_click_stats(self, link_id):
        """Get click statistics"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT total_clicks FROM utm_links WHERE id = %s", (link_id,))
            link_data = cur.fetchone()
            
            cur.execute("""
                SELECT DATE(clicked_at) as date, COUNT(*) as count
                FROM clicks
                WHERE link_id = %s
                GROUP BY DATE(clicked_at)
                ORDER BY date ASC
            """, (link_id,))
            timeline = cur.fetchall()
            
            cur.execute("""
                SELECT clicked_at, ip_address, country, user_agent
                FROM clicks
                WHERE link_id = %s
                ORDER BY clicked_at DESC
                LIMIT 20
            """, (link_id,))
            recent_clicks = cur.fetchall()
            
            cur.close()
            conn.close()
            
            return {
                'total_clicks': link_data['total_clicks'] if link_data else 0,
                'timeline': [{'date': str(row['date']), 'count': row['count']} for row in timeline],
                'recent_clicks': [dict(row) for row in recent_clicks]
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return {'total_clicks': 0, 'timeline': [], 'recent_clicks': []}