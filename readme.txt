# ============================================================================
# PROJECT STRUCTURE
# ============================================================================
"""
Updated project structure with PJSIP in endpoints app:

├── apps/
│   └── endpoints/
│       ├── __init__.py
│       ├── routes.py                    # Main endpoints routes + PJSIP routes
│       ├── schemas.py                   # PJSIP Pydantic models
│       ├── dependencies.py              # Endpoints-specific dependencies
│       ├── pjsip_manager/              # PJSIP template management
│       │   ├── __init__.py
│       │   ├── template_manager.py     # Template management logic
│       │   ├── config_manager.py       # Configuration file management
│       │   └── tasks.py                # Background tasks (Asterisk reload)
│       └── templates/                   # Default PJSIP templates (optional)
│           ├── endpoint-basic.yaml
│           ├── auth-basic.yaml
│           └── aor-basic.yaml
├── config.py                           # Global config (add PJSIP settings)
├── shared/
│   ├── utils/                          # Shared utilities
│   │   ├── backup.py                   # Backup utilities
│   │   ├── validation.py               # Config validation utilities
│   │   └── asterisk.py                 # Asterisk integration utilities
│   └── models.py                       # Add base PJSIP models here
└── dependencies.py                     # Global dependencies
"""

# Template Management
POST   /api/v1/endpoints/templates           # Create template
GET    /api/v1/endpoints/templates           # List templates
GET    /api/v1/endpoints/templates/{name}    # Get template
PUT    /api/v1/endpoints/templates/{name}    # Update template
DELETE /api/v1/endpoints/templates/{name}    # Delete template

# PJSIP Endpoint Management
POST   /api/v1/endpoints/pjsip               # Create PJSIP endpoint
POST   /api/v1/endpoints/pjsip/bulk          # Bulk create endpoints
GET    /api/v1/endpoints/pjsip               # List PJSIP endpoints
GET    /api/v1/endpoints/pjsip/{id}/config   # Get endpoint config
POST   /api/v1/endpoints/pjsip/{id}/validate # Validate endpoint ✅
DELETE /api/v1/endpoints/pjsip/{id}          # Delete endpoint

# Utilities  
POST   /api/v1/endpoints/pjsip/render-template # Preview templates
POST   /api/v1/endpoints/pjsip/reload          # Reload Asterisk
GET    /api/v1/endpoints/pjsip/health          # Health check
GET    /api/v1/endpoints/pjsip/stats           # Statistics

# Your Existing Endpoints (unchanged)
GET    /api/v1/endpoints/                    # Your existing routes
POST   /api/v1/endpoints/                    # Your existing routes




# ============================================================================
# CURL COMMAND EXAMPLES
# ============================================================================

# Create internal phone
curl -X POST "http://localhost:8000/api/v1/pjsip/endpoints" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "1001",
    "template": "endpoint-internal",
    "variables": {
      "secret": "myPassword123",
      "callerid_name": "John Doe",
      "mailbox": "1001@default"
    },
    "auth_config": {
      "template": "auth-basic",
      "secret": "myPassword123"
    },
    "aor_config": {
      "template": "aor-basic"
    }
  }'

# Create SIP trunk
curl -X POST "http://localhost:8000/api/v1/pjsip/endpoints" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "trunk-provider",
    "template": "endpoint-trunk",
    "variables": {
      "trunk_host": "sip.provider.com",
      "use_auth": true,
      "from_user": "myaccount"
    },
    "auth_config": {
      "template": "auth-basic",
      "username": "myaccount",
      "secret": "trunkPassword"
    },
    "aor_config": {
      "template": "aor-trunk",
      "trunk_host": "sip.provider.com",
      "trunk_port": "5060"
    }
  }'

# ============================================================================
# PYTHON SCRIPT FOR BULK ENDPOINT CREATION
# ============================================================================

import requests
import json

BASE_URL = "http://localhost:8000/api/v1/pjsip"

def create_endpoint(endpoint_data):
    """Create a single endpoint"""
    try:
        response = requests.post(f"{BASE_URL}/endpoints", json=endpoint_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Created endpoint: {endpoint_data['id']}")
            print(f"   File: {result.get('file_path')}")
            print(f"   Sections: {result.get('sections_generated')}")
            return True
        else:
            print(f"❌ Failed to create {endpoint_data['id']}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating {endpoint_data['id']}: {e}")
        return False

def create_phone_range(start_ext, end_ext, password_prefix="pass"):
    """Create a range of phone extensions"""
    endpoints_created = 0
    
    for ext in range(start_ext, end_ext + 1):
        endpoint_data = {
            "id": str(ext),
            "template": "endpoint-internal",
            "variables": {
                "secret": f"{password_prefix}{ext}",
                "callerid_name": f"Extension {ext}",
                "mailbox": f"{ext}@default"
            },
            "auth_config": {
                "template": "auth-basic",
                "secret": f"{password_prefix}{ext}"
            },
            "aor_config": {
                "template": "aor-basic"
            }
        }
        
        if create_endpoint(endpoint_data):
            endpoints_created += 1
    
    print(f"\n📊 Created {endpoints_created} out of {end_ext - start_ext + 1} endpoints")

def create_department_phones():
    """Create phones for different departments"""
    departments = {
        "sales": {"range": (2001, 2010), "context": "sales"},
        "support": {"range": (3001, 3005), "context": "support"}, 
        "management": {"range": (4001, 4003), "context": "management"}
    }
    
    for dept, config in departments.items():
        start, end = config["range"]
        print(f"\n🏢 Creating {dept.upper()} department phones ({start}-{end})")
        
        for ext in range(start, end + 1):
            endpoint_data = {
                "id": str(ext),
                "template": "endpoint-internal",
                "variables": {
                    "secret": f"{dept}{ext}pass",
                    "callerid_name": f"{dept.title()} {ext}",
                    "mailbox": f"{ext}@{dept}",
                    "context": config["context"],
                    "accountcode": dept.upper()
                },
                "auth_config": {
                    "template": "auth-md5",
                    "secret": f"{dept}{ext}pass",
                    "realm": f"{dept}.company.com"
                },
                "aor_config": {
                    "template": "aor-basic",
                    "qualify_frequency": "30"
                }
            }
            
            create_endpoint(endpoint_data)

# Usage examples
if __name__ == "__main__":
    # Create phones 1001-1010
    create_phone_range(1001, 1010)
    
    # Create department phones
    create_department_phones()
    
    # Create a trunk
    trunk_data = {
        "id": "trunk-main",
        "template": "endpoint-trunk",
        "variables": {
            "trunk_host": "sip.myprovider.com",
            "use_auth": True,
            "from_user": "myaccount"
        },
        "auth_config": {
            "template": "auth-basic",
            "username": "myaccount",
            "secret": "mytrunkpassword"
        },
        "aor_config": {
            "template": "aor-trunk",
            "trunk_host": "sip.myprovider.com",
            "trunk_port": "5060"
        }
    }
    
    create_endpoint(trunk_data)

# ============================================================================
# VALIDATION AND TESTING
# ============================================================================

# After creating endpoints, you can:

# 1. List all endpoints
curl -X GET "http://localhost:8000/api/v1/pjsip/endpoints"

# 2. Get specific endpoint config
curl -X GET "http://localhost:8000/api/v1/pjsip/endpoints/1001/config"

# 3. Validate endpoint
curl -X POST "http://localhost:8000/api/v1/pjsip/endpoints/validate/1001"

# 4. Delete endpoint
curl -X DELETE "http://localhost:8000/api/v1/pjsip/endpoints/1001"

# ============================================================================
# EXPECTED GENERATED CONFIGURATION EXAMPLE
# ============================================================================

# For the basic internal phone endpoint above, this generates:
# File: /etc/asterisk/pjsip.d/includes/1001.conf

"""
; Generated endpoint configuration for 1001
; Generated at: 2025-06-12T15:30:45
; Template: endpoint-internal

[1001](endpoint-internal-tpl)
type=endpoint
context=internal
disallow=all
allow=ulaw,alaw,g722
auth=1001-auth
aors=1001
direct_media=yes
trust_id_outbound=yes
device_state_busy_at=1
dtmf_mode=rfc4733
ice_support=yes
force_rport=yes
rewrite_contact=yes
rtp_symmetric=yes
send_pai=yes
callerid=John Doe <1001>
mailboxes=1001@default

[1001-auth]
type=auth
auth_type=userpass
username=1001
password=myPassword123

[1001]
type=aor
max_contacts=2
remove_existing=yes
qualify_frequency=30
"""

# And adds this line to /etc/asterisk/pjsip.conf:
# #include "/etc/asterisk/pjsip.d/includes/1001.conf"



Payload Structure Explained
Required Fields:

id - Unique endpoint identifier
template - Template name to use
variables - Variables for template rendering

Optional Sections:

auth_config - Authentication configuration
aor_config - Address of Record configuration
transport_config - Transport settings
overrides - Direct option overrides

Variable Inheritance:
Variables flow like this:

Template default values (lowest priority)
Parent template defaults
variables section
overrides section (highest priority)

Common Use Cases
Internal Phone with Voicemail:
json{
  "id": "2001",
  "template": "endpoint-internal",
  "variables": {
    "secret": "emp2001pass",
    "callerid_name": "Alice Smith",
    "mailbox": "2001@sales",
    "context": "internal",
    "accountcode": "SALES"
  },
  "auth_config": {
    "template": "auth-md5",
    "secret": "emp2001pass",
    "realm": "company.com"
  },
  "aor_config": {
    "template": "aor-basic",
    "max_contacts": "2",
    "qualify_frequency": "30"
  }
}
Mobile/Multi-Device User:
json{
  "id": "mobile-1001",
  "template": "endpoint-internal", 
  "variables": {
    "secret": "mobileUser123",
    "callerid_name": "Bob Mobile"
  },
  "auth_config": {
    "template": "auth-md5",
    "secret": "mobileUser123"
  },
  "aor_config": {
    "template": "aor-multicontact",
    "max_contacts": "5",
    "default_expiration": "3600"
  }
}
Conference Room:
json{
  "id": "conf-boardroom",
  "template": "endpoint-conference",
  "variables": {
    "secret": "boardroomAccess",
    "callerid_name": "Board Room",
    "conference_room": "BOARDROOM"
  },
  "auth_config": {
    "template": "auth-basic",
    "secret": "boardroomAccess"
  },
  "aor_config": {
    "template": "aor-basic",
    "max_contacts": "10"
  }
}
What Gets Generated
When you create an endpoint, the system:

Renders the template with your variables
Creates include file at /etc/asterisk/pjsip.d/includes/{id}.conf
Updates main pjsip.conf with #include directive
Creates backup (if enabled)
Validates configuration (if enabled)
Returns result with file path and validation status

Example Generated Config:
ini; Generated endpoint configuration for 1001
; Generated at: 2025-06-12T15:30:45
; Template: endpoint-internal

[1001](endpoint-internal-tpl)
type=endpoint
context=internal
allow=ulaw,alaw,g722
auth=1001-auth
aors=1001
callerid=John Doe <1001>
mailboxes=1001@default

[1001-auth]
type=auth
auth_type=userpass
username=1001
password=myPassword123

[1001]
type=aor
max_contacts=1
remove_existing=yes
qualify_frequency=60
Testing Your Endpoints
After creation, test with:
bash# List all endpoints
curl -X GET "http://localhost:8000/api/v1/pjsip/endpoints"

# Get endpoint configuration
curl -X GET "http://localhost:8000/api/v1/pjsip/endpoints/1001/config"

# Validate endpoint
curl -X POST "http://localhost:8000/api/v1/pjsip/endpoints/validate/1001"

Enhanced Filtering Capabilities
Primary Filters:

id - Partial match on endpoint ID
ids - Exact match on specific IDs (comma-separated)
type - Endpoint type (endpoint, trunk, webrtc, conference)
username - Partial match on auth username
auth_type - Authentication type (userpass, md5, oauth)

Configuration Filters:

context - Dialplan context
accountcode - Account code
transport - Transport type (udp, tcp, tls)
callerid - Caller ID (partial match)
template_used - Template used to create endpoint

Advanced Filters:

max_contacts_gte/lte - Range filters for max contacts
direct_media - Boolean filter for direct media
webrtc_enabled - Boolean filter for WebRTC support
recording_enabled - Boolean filter for call recording
created_after/before - Date range filters

Usage Examples:
1. Filter by ID pattern:
bashGET /api/v1/endpoints/pjsip/structured?id=100
# Returns: 1001, 1002, 1003, etc.
2. Get specific endpoints:
bashGET /api/v1/endpoints/pjsip/structured?ids=1001,1002,trunk-provider
3. Filter by type and auth:
bashGET /api/v1/endpoints/pjsip/structured?type=webrtc&auth_type=md5
4. Filter by username pattern:
bashGET /api/v1/endpoints/pjsip/structured?username=john
# Returns endpoints with usernames like "john", "johnson", etc.
5. Complex filtering:
bashGET /api/v1/endpoints/pjsip/structured?context=internal&recording_enabled=true&max_contacts_gte=2&sort_by=username_asc
6. Get available filter options:
bashGET /api/v1/endpoints/pjsip/filters/options
Response:
json{
  "available_contexts": ["internal", "external", "from-trunk"],
  "available_auth_types": ["userpass", "md5"],
  "available_transports": ["udp", "tcp", "tls"],
  "available_templates": ["basic-phone", "endpoint-internal", "endpoint-trunk"],
  "available_accountcodes": ["SALES", "SUPPORT", "MANAGEMENT"],
  "endpoint_types": ["endpoint", "trunk", "webrtc", "conference", "all"],
  "sort_options": ["id_asc", "id_desc", "username_asc", "username_desc"],
  "total_endpoints": 50
}
Sorting Options:

id_asc/desc - Sort by endpoint ID
username_asc/desc - Sort by auth username
created_asc/desc - Sort by creation date
context_asc/desc - Sort by dialplan context

Pagination with Metadata:
json{
  "endpoints": [...],
  "total_count": 100,       // Total endpoints before filtering
  "filtered_count": 15,     // Endpoints after filtering
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "filters_applied": {      // Shows what filters were used
    "type": "webrtc",
    "context": "internal"
  },
  "sort_by": "id_asc"
}
Smart Type Detection:
The system automatically detects endpoint types based on:

Template name patterns
Configuration patterns (WebRTC settings, trunk contexts)
Naming conventions

Real-World Examples:
Find all sales team phones:
bashGET /api/v1/endpoints/pjsip/structured?accountcode=SALES&context=internal
Find problematic WebRTC endpoints:
bashGET /api/v1/endpoints/pjsip/structured?type=webrtc&max_contacts_gte=5
Find all trunk connections:
bashGET /api/v1/endpoints/pjsip/structured?type=trunk&auth_type=userpass
Find endpoints needing password updates:
bashGET /api/v1/endpoints/pjsip/structured?auth_type=userpass&created_before=2025-01-01