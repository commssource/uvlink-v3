#!/usr/bin/env python3
"""
Script to create PJSIP Jinja2 template files
Run this script to set up your template directory structure
"""

import os
from pathlib import Path

# Template definitions
TEMPLATES = {
    'endpoint-basic.j2': '''[{{ endpoint_id }}]({{ template_name | default('endpoint-basic-tpl') }})
type=endpoint
{% if context -%}
context={{ context }}
{% endif -%}
{% if auth_id -%}
auth={{ auth_id }}
{% endif -%}
{% if aor_id -%}
aors={{ aor_id }}
{% endif -%}
{% if transport -%}
transport={{ transport }}
{% endif -%}
{% if callerid -%}
callerid={{ callerid }}
{% endif -%}
{% if accountcode -%}
accountcode={{ accountcode }}
{% endif -%}
{% if allow -%}
allow={{ allow }}
{% else -%}
allow=ulaw,alaw
{% endif -%}
{% if disallow -%}
disallow={{ disallow }}
{% else -%}
disallow=all
{% endif -%}
{% if dtmf_mode -%}
dtmf_mode={{ dtmf_mode }}
{% else -%}
dtmf_mode=rfc4733
{% endif -%}
{% if direct_media is defined -%}
direct_media={{ direct_media | lower }}
{% else -%}
direct_media=no
{% endif -%}
{% if rtp_symmetric -%}
rtp_symmetric={{ rtp_symmetric }}
{% else -%}
rtp_symmetric=yes
{% endif -%}
{% if force_rport -%}
force_rport={{ force_rport }}
{% else -%}
force_rport=yes
{% endif -%}
{% if rewrite_contact -%}
rewrite_contact={{ rewrite_contact }}
{% else -%}
rewrite_contact=yes
{% endif -%}
{% if ice_support -%}
ice_support={{ ice_support }}
{% else -%}
ice_support=no
{% endif -%}
{% if device_state_busy_at -%}
device_state_busy_at={{ device_state_busy_at }}
{% else -%}
device_state_busy_at=1
{% endif -%}
{% if mailboxes -%}
mailboxes={{ mailboxes }}
{% endif -%}
{% if send_pai -%}
send_pai={{ send_pai }}
{% else -%}
send_pai=yes
{% endif -%}
{% if send_rpid -%}
send_rpid={{ send_rpid }}
{% else -%}
send_rpid=yes
{% endif -%}
{% if allow_subscribe -%}
allow_subscribe={{ allow_subscribe }}
{% else -%}
allow_subscribe=yes
{% endif -%}
{% if rtp_timeout -%}
rtp_timeout={{ rtp_timeout }}
{% else -%}
rtp_timeout=30
{% endif -%}
{% if rtp_timeout_hold -%}
rtp_timeout_hold={{ rtp_timeout_hold }}
{% else -%}
rtp_timeout_hold=60
{% endif -%}
{% if set_var -%}
set_var={{ set_var }}
{% endif -%}
{% if webrtc -%}
webrtc={{ webrtc }}
{% endif -%}
{% if media_encryption -%}
media_encryption={{ media_encryption }}
{% endif -%}''',

    'endpoint-webrtc.j2': '''[{{ endpoint_id }}]({{ template_name | default('endpoint-webrtc-tpl') }})
type=endpoint
{% if context %}context={{ context }}{% endif %}
{% if auth_id %}auth={{ auth_id }}{% endif %}
{% if aor_id %}aors={{ aor_id }}{% endif %}
transport=transport-wss
{% if callerid %}callerid={{ callerid }}{% endif %}
allow=opus,ulaw,alaw
disallow=all
dtmf_mode=rfc4733
webrtc=yes
media_encryption=dtls
dtls_auto_generate_cert=yes
ice_support=yes
use_avpf=yes
media_use_received_transport=yes
rtcp_mux=yes
direct_media=no
force_rport=yes
rewrite_contact=yes
{% if device_state_busy_at %}device_state_busy_at={{ device_state_busy_at }}{% else %}device_state_busy_at=1{% endif %}
{% if mailboxes %}mailboxes={{ mailboxes }}{% endif %}
send_pai=yes
send_rpid=yes
allow_subscribe=yes
rtp_timeout=30
rtp_timeout_hold=60
{% if set_var %}set_var={{ set_var }}{% endif %}''',

    'endpoint-trunk.j2': '''[{{ endpoint_id }}]({{ template_name | default('endpoint-trunk-tpl') }})
type=endpoint
context=from-trunk
{% if auth_id %}auth={{ auth_id }}{% endif %}
{% if aor_id %}aors={{ aor_id }}{% endif %}
{% if transport %}transport={{ transport }}{% else %}transport=transport-udp{% endif %}
{% if callerid %}callerid={{ callerid }}{% endif %}
{% if accountcode %}accountcode={{ accountcode }}{% endif %}
allow=ulaw,alaw,g729
disallow=all
dtmf_mode=rfc4733
direct_media=yes
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
ice_support=no
trust_id_inbound=yes
trust_id_outbound=yes
send_pai=yes
send_rpid=yes
allow_subscribe=no
rtp_timeout=60
rtp_timeout_hold=300
{% if set_var %}set_var={{ set_var }}{% endif %}''',

    'auth-basic.j2': '''[{{ auth_id | default(endpoint_id + '-auth') }}]({{ auth_template | default('auth-basic-tpl') }})
type=auth
auth_type={{ auth_type | default('userpass') }}
{% if username -%}
username={{ username }}
{% else -%}
username={{ endpoint_id }}
{% endif -%}
{% if password -%}
password={{ password }}
{% endif -%}
{% if realm -%}
realm={{ realm }}
{% endif -%}''',

    'aor-basic.j2': '''[{{ aor_id | default(endpoint_id) }}]({{ aor_template | default('aor-basic-tpl') }})
type=aor
{% if max_contacts -%}
max_contacts={{ max_contacts }}
{% else -%}
max_contacts=1
{% endif -%}
{% if qualify_timeout -%}
qualify_timeout={{ qualify_timeout }}
{% else -%}
qualify_timeout=3
{% endif -%}
{% if qualify_frequency -%}
qualify_frequency={{ qualify_frequency }}
{% else -%}
qualify_frequency=60
{% endif -%}
{% if authenticate_qualify -%}
authenticate_qualify={{ authenticate_qualify }}
{% else -%}
authenticate_qualify=no
{% endif -%}
{% if default_expiration -%}
default_expiration={{ default_expiration }}
{% else -%}
default_expiration=3600
{% endif -%}
{% if minimum_expiration -%}
minimum_expiration={{ minimum_expiration }}
{% else -%}
minimum_expiration=60
{% endif -%}
{% if maximum_expiration -%}
maximum_expiration={{ maximum_expiration }}
{% else -%}
maximum_expiration=7200
{% endif -%}
{% if remove_existing -%}
remove_existing={{ remove_existing }}
{% else -%}
remove_existing=yes
{% endif -%}''',

    'aor-trunk.j2': '''[{{ aor_id | default(endpoint_id) }}]({{ aor_template | default('aor-trunk-tpl') }})
type=aor
{% if contact %}contact={{ contact }}{% endif %}
max_contacts=1
qualify_timeout=10
qualify_frequency=30
authenticate_qualify=no
default_expiration=3600
minimum_expiration=60
maximum_expiration=7200
remove_existing=yes''',

    'transport-udp.j2': '''[{{ transport_id | default('transport-udp') }}]({{ transport_template | default('transport-udp-tpl') }})
type=transport
protocol=udp
{% if bind %}bind={{ bind }}{% else %}bind=0.0.0.0:5060{% endif %}
{% if external_media_address %}external_media_address={{ external_media_address }}{% endif %}
{% if external_signaling_address %}external_signaling_address={{ external_signaling_address }}{% endif %}
{% if local_net %}local_net={{ local_net }}{% endif %}''',

    'transport-tcp.j2': '''[{{ transport_id | default('transport-tcp') }}]({{ transport_template | default('transport-tcp-tpl') }})
type=transport
protocol=tcp
{% if bind %}bind={{ bind }}{% else %}bind=0.0.0.0:5060{% endif %}
{% if external_media_address %}external_media_address={{ external_media_address }}{% endif %}
{% if external_signaling_address %}external_signaling_address={{ external_signaling_address }}{% endif %}
{% if local_net %}local_net={{ local_net }}{% endif %}''',

    'transport-wss.j2': '''[{{ transport_id | default('transport-wss') }}]({{ transport_template | default('transport-wss-tpl') }})
type=transport
protocol=wss
{% if bind %}bind={{ bind }}{% else %}bind=0.0.0.0:8089{% endif %}
{% if cert_file %}cert_file={{ cert_file }}{% endif %}
{% if priv_key_file %}priv_key_file={{ priv_key_file }}{% endif %}
{% if ca_list_file %}ca_list_file={{ ca_list_file }}{% endif %}''',

    'identify-basic.j2': '''[{{ identify_id | default(endpoint_id + '-identify') }}]({{ identify_template | default('identify-basic-tpl') }})
type=identify
endpoint={{ endpoint_id }}
{% if match %}match={{ match }}{% endif %}''',

    'contact-basic.j2': '''[{{ contact_id | default(endpoint_id + '-contact') }}]({{ contact_template | default('contact-basic-tpl') }})
type=contact
{% if uri %}uri={{ uri }}{% endif %}
{% if expiration_time %}expiration_time={{ expiration_time }}{% else %}expiration_time=3600{% endif %}
{% if qualify_frequency %}qualify_frequency={{ qualify_frequency }}{% else %}qualify_frequency=60{% endif %}''',

    'registration-basic.j2': '''[{{ registration_id | default(endpoint_id + '-reg') }}]({{ registration_template | default('registration-basic-tpl') }})
type=registration
{% if server_uri %}server_uri={{ server_uri }}{% endif %}
{% if client_uri %}client_uri={{ client_uri }}{% endif %}
{% if contact_user %}contact_user={{ contact_user }}{% endif %}
{% if transport %}transport={{ transport }}{% endif %}
{% if outbound_auth %}outbound_auth={{ outbound_auth }}{% endif %}
{% if retry_interval %}retry_interval={{ retry_interval }}{% else %}retry_interval=60{% endif %}
{% if max_retries %}max_retries={{ max_retries }}{% else %}max_retries=10{% endif %}
{% if auth_rejection_permanent %}auth_rejection_permanent={{ auth_rejection_permanent }}{% else %}auth_rejection_permanent=yes{% endif %}'''
}

def create_template_files(base_dir="templates/pjsip"):
    """Create template files in the specified directory"""
    template_dir = Path(base_dir)
    template_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating template files in: {template_dir.absolute()}")
    
    for filename, content in TEMPLATES.items():
        file_path = template_dir / filename
        
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✓ Created: {filename}")
        except Exception as e:
            print(f"✗ Failed to create {filename}: {e}")
    
    print(f"\nTemplate setup complete! Created {len(TEMPLATES)} template files.")
    print(f"Template directory: {template_dir.absolute()}")

if __name__ == "__main__":
    import sys
    
    # Allow custom base directory as command line argument
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "templates/pjsip"
    create_template_files(base_dir)