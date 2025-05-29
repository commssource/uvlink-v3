# Endpoints API Documentation

## Overview
The Endpoints API provides a structured interface for managing PJSIP endpoints in Asterisk. The API supports both simple and advanced endpoint configurations, with a focus on organized, logical grouping of settings.

## Base URL
```
/api/v1/endpoints
```

## Authentication
All endpoints require authentication using a valid API key in the `X-API-Key` header.

## Endpoints

### List All Endpoints
```http
GET /api/v1/endpoints
```

#### Response
```json
{
  "success": true,
  "count": 2,
  "endpoints": [
    {
      "id": "1001",
      "type": "endpoint",
      "name": "Extension 1001",
      "accountcode": "1001",
      "audio_media": {
        "max_audio_streams": 2,
        "allow": "ulaw,alaw",
        "disallow": "all",
        "moh_suggest": "default",
        "tone_zone": "us",
        "dtmf_mode": "rfc4733",
        "allow_transfer": "yes"
      },
      "transport_network": {
        "transport": "transport-udp",
        "identify_by": "username",
        "force_rport": "yes",
        "rewrite_contact": "yes",
        "direct_media": "no",
        "ice_support": "no",
        "webrtc": "no"
      },
      "rtp": {
        "rtp_symmetric": "yes",
        "rtp_timeout": 30,
        "rtp_timeout_hold": 60,
        "sdp_session": "Asterisk"
      },
      "recording": {
        "record_calls": "yes",
        "one_touch_recording": "yes",
        "record_on_feature": "*1",
        "record_off_feature": "*2"
      },
      "call": {
        "context": "internal",
        "callerid": "",
        "call_group": "1",
        "pickup_group": "1",
        "device_state_busy_at": 2
      },
      "presence": {
        "allow_subscribe": "yes",
        "send_pai": "yes",
        "send_rpid": "yes",
        "100rel": "no"
      },
      "voicemail": {
        "mailboxes": "",
        "voicemail_extension": ""
      },
      "auth": {
        "type": "auth",
        "auth_type": "userpass",
        "username": "1001",
        "password": "secret"
      },
      "aor": {
        "type": "aor",
        "max_contacts": 1,
        "qualify_frequency": 60
      }
    }
  ]
}
```

### Create Endpoint
```http
POST /api/v1/endpoints
```

#### Request Body
```json
{
  "id": "1001",
  "type": "endpoint",
  "name": "Extension 1001",
  "audio_media": {
    "max_audio_streams": 2,
    "allow": "ulaw,alaw",
    "disallow": "all",
    "moh_suggest": "default",
    "tone_zone": "us",
    "dtmf_mode": "rfc4733",
    "allow_transfer": "yes"
  },
  "transport_network": {
    "transport": "transport-udp",
    "identify_by": "username",
    "force_rport": "yes",
    "rewrite_contact": "yes",
    "direct_media": "no",
    "ice_support": "no",
    "webrtc": "no"
  },
  "rtp": {
    "rtp_symmetric": "yes",
    "rtp_timeout": 30,
    "rtp_timeout_hold": 60,
    "sdp_session": "Asterisk"
  },
  "recording": {
    "record_calls": "yes",
    "one_touch_recording": "yes",
    "record_on_feature": "*1",
    "record_off_feature": "*2"
  },
  "call": {
    "context": "internal",
    "callerid": "",
    "call_group": "1",
    "pickup_group": "1",
    "device_state_busy_at": 2
  },
  "presence": {
    "allow_subscribe": "yes",
    "send_pai": "yes",
    "send_rpid": "yes",
    "100rel": "no"
  },
  "voicemail": {
    "mailboxes": "",
    "voicemail_extension": ""
  },
  "auth": {
    "type": "auth",
    "auth_type": "userpass",
    "username": "1001",
    "password": "secret"
  },
  "aor": {
    "type": "aor",
    "max_contacts": 1,
    "qualify_frequency": 60
  }
}
```

#### Response
```json
{
  "success": true,
  "message": "Endpoint created successfully",
  "endpoint_id": "1001"
}
```

### Update Endpoint
```http
PUT /api/v1/endpoints/{endpoint_id}
```

#### Request Body
```json
{
  "name": "Updated Extension 1001",
  "audio_media": {
    "allow": "ulaw,alaw,g722"
  },
  "transport_network": {
    "webrtc": "yes"
  }
}
```

#### Response
```json
{
  "success": true,
  "message": "Endpoint updated successfully"
}
```

### Delete Endpoint
```http
DELETE /api/v1/endpoints/{endpoint_id}
```

#### Response
```json
{
  "success": true,
  "message": "Endpoint deleted successfully"
}
```

## Configuration Sections

### Audio/Media Settings
- `max_audio_streams`: Maximum number of audio streams (1-10)
- `allow`: Allowed codecs (comma-separated)
- `disallow`: Disallowed codecs
- `moh_suggest`: Music on Hold suggestion
- `tone_zone`: Tone zone for DTMF
- `dtmf_mode`: DTMF mode (rfc4733, inband, info)
- `allow_transfer`: Allow call transfers (yes/no)

### Transport/Network Settings
- `transport`: Transport protocol
- `identify_by`: Identification method
- `force_rport`: Force RPort (yes/no)
- `rewrite_contact`: Rewrite Contact header (yes/no)
- `direct_media`: Direct media (yes/no)
- `ice_support`: ICE support (yes/no)
- `webrtc`: WebRTC support (yes/no)

### RTP Settings
- `rtp_symmetric`: RTP symmetric mode (yes/no)
- `rtp_timeout`: RTP timeout in seconds (0-300)
- `rtp_timeout_hold`: RTP timeout hold in seconds (0-3600)
- `sdp_session`: SDP session name

### Recording Settings
- `record_calls`: Enable call recording (yes/no)
- `one_touch_recording`: Enable one-touch recording (yes/no)
- `record_on_feature`: Feature code to start recording
- `record_off_feature`: Feature code to stop recording

### Call Settings
- `context`: Dialplan context
- `callerid`: Caller ID
- `callerid_privacy`: Caller ID privacy
- `connected_line_method`: Connected line method
- `call_group`: Call group
- `pickup_group`: Pickup group
- `device_state_busy_at`: Device state busy threshold (1-10)

### Presence Settings
- `allow_subscribe`: Allow subscriptions (yes/no)
- `send_pai`: Send P-Asserted-Identity (yes/no)
- `send_rpid`: Send Remote-Party-ID (yes/no)
- `100rel`: 100rel support (yes/no)

### Authentication
- `type`: Type (auth)
- `auth_type`: Authentication type (userpass)
- `username`: Username (max 50 chars)
- `password`: Password (max 128 chars)
- `realm`: Authentication realm

### Address of Record (AOR)
- `type`: Type (aor)
- `max_contacts`: Maximum contacts (1-10)
- `qualify_frequency`: Qualification frequency (0-300)
- `authenticate_qualify`: Authenticate qualify (yes/no)
- `default_expiration`: Default expiration
- `minimum_expiration`: Minimum expiration
- `maximum_expiration`: Maximum expiration

## Error Responses

### Validation Error
```json
{
  "success": false,
  "message": "Validation failed",
  "errors": [
    "ID must contain only letters, numbers, underscores, and hyphens",
    "Auth username is required",
    "AOR max_contacts must be between 1 and 10"
  ],
  "warnings": [
    "Unknown codec: invalid_codec"
  ]
}
```

### Not Found Error
```json
{
  "success": false,
  "message": "Endpoint not found",
  "endpoint_id": "1001"
}
```

### Server Error
```json
{
  "success": false,
  "message": "Internal server error",
  "error": "Error message"
}
``` 