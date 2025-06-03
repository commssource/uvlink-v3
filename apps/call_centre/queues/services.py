import os
from typing import List, Optional, Dict
from .schemas import QueueConfig, QueueMember, QueueListResponse

class QueueService:
    def __init__(self, queue_path: str):
        self.queue_path = queue_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        # Create the file if it doesn't exist
        if not os.path.exists(queue_path):
            with open(queue_path, 'w') as f:
                f.write("")

    def _format_member_line(self, member: QueueMember) -> str:
        return f"member => Local/{member.extension}@static-member-{member.extension}/n,{member.penalty},PJSIP/{member.interface},hint:{member.hint}"

    def _parse_member_line(self, line: str) -> Optional[QueueMember]:
        """Parse a member line from the queue configuration"""
        try:
            # Example line: member => Local/207@static-member-207/n,0,PJSIP/200207,hint:207@t-200
            parts = line.strip().split(',')
            if len(parts) < 3:
                return None
            
            member_part = parts[0].split('@')[0].split('/')[-1]
            penalty = int(parts[1])
            interface = parts[2].split('/')[-1]
            hint = parts[3].split(':')[-1]
            
            return QueueMember(
                extension=member_part,
                interface=interface,
                hint=hint,
                penalty=penalty
            )
        except Exception:
            return None

    def _parse_queue_section(self, section: str) -> Optional[QueueConfig]:
        """Parse a queue section from the configuration file"""
        try:
            lines = section.strip().split('\n')
            if not lines:
                return None

            # Get queue name from first line
            queue_name = lines[0].strip('[]')
            
            # Parse configuration
            config: Dict = {}
            members: List[QueueMember] = []
            
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('member =>'):
                    member = self._parse_member_line(line)
                    if member:
                        members.append(member)
                else:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Convert boolean values
                    if value.lower() in ['yes', 'no']:
                        value = value.lower() == 'yes'
                    # Convert numeric values
                    elif value.isdigit():
                        value = int(value)
                    
                    config[key] = value

            return QueueConfig(
                name=queue_name,
                context=config.get('context', ''),
                cbcontext=config.get('cbcontext', ''),
                setinterfacevar=config.get('setinterfacevar', True),
                maxlen=config.get('maxlen', 4),
                timeout=config.get('timeout', 300),
                joinempty=config.get('joinempty', True),
                leavewhenempty=config.get('leavewhenempty', False),
                announce_holdtime=config.get('announce-holdtime', True),
                announce_position=config.get('announce-position', True),
                announce_frequency=config.get('announce-frequency', 30),
                announce_round_seconds=config.get('announce-round-seconds', 0),
                members=members,
                strategy=config.get('strategy', 'ringall'),
                autofill=config.get('autofill', True),
                ringinuse=config.get('ringinuse', False),
                retry=config.get('retry', 4),
                wrapuptime=config.get('wrapuptime', 4),
                announce=config.get('announce', '')
            )
        except Exception as e:
            print(f"Error parsing queue section: {e}")
            return None

    def _queue_to_config(self, queue: QueueConfig) -> str:
        config_lines = [
            f"[{queue.name}]",
            f"context={queue.context}",
            f"cbcontext={queue.cbcontext}",
            f"setinterfacevar={'yes' if queue.setinterfacevar else 'no'}",
            f"maxlen={queue.maxlen}",
            f"timeout={queue.timeout}",
            f"joinempty={'yes' if queue.joinempty else 'no'}",
            f"leavewhenempty={'yes' if queue.leavewhenempty else 'no'}",
            f"announce-holdtime={'yes' if queue.announce_holdtime else 'no'}",
            f"announce-position={'yes' if queue.announce_position else 'no'}",
            f"announce-frequency={queue.announce_frequency}",
            f"announce-round-seconds={queue.announce_round_seconds}",
        ]

        # Add members
        for member in queue.members:
            config_lines.append(self._format_member_line(member))

        config_lines.extend([
            f"strategy={queue.strategy}",
            f"autofill={'yes' if queue.autofill else 'no'}",
            f"ringinuse={'yes' if queue.ringinuse else 'no'}",
            f"retry={queue.retry}",
            f"wrapuptime={queue.wrapuptime}",
            f"announce={queue.announce}"
        ])

        return "\n".join(config_lines)

    def create_queue(self, queue: QueueConfig) -> bool:
        """Create a new queue configuration"""
        try:
            # Read existing content
            existing_content = ""
            if os.path.exists(self.queue_path):
                with open(self.queue_path, 'r') as f:
                    existing_content = f.read()

            # Check if queue already exists
            if f"[{queue.name}]" in existing_content:
                return False

            # Append new queue configuration
            with open(self.queue_path, 'a') as f:
                if existing_content and not existing_content.endswith('\n\n'):
                    f.write('\n\n')
                f.write(self._queue_to_config(queue))
            return True
        except Exception as e:
            print(f"Error creating queue: {e}")
            return False

    def get_queue(self, queue_name: str) -> Optional[QueueConfig]:
        """Get queue configuration by name"""
        try:
            if not os.path.exists(self.queue_path):
                return None

            with open(self.queue_path, 'r') as f:
                content = f.read()
            
            queue_sections = content.split("\n\n")
            for section in queue_sections:
                if section.startswith(f"[{queue_name}]"):
                    return self._parse_queue_section(section)
            return None
        except Exception as e:
            print(f"Error reading queue: {e}")
            return None

    def update_queue(self, old_name: str, queue: QueueConfig) -> bool:
        """Update an existing queue configuration"""
        try:
            if not os.path.exists(self.queue_path):
                return False

            with open(self.queue_path, 'r') as f:
                content = f.read()
            
            queue_sections = content.split("\n\n")
            new_sections = []
            updated = False
            
            for section in queue_sections:
                if section.startswith(f"[{old_name}]"):
                    new_sections.append(self._queue_to_config(queue))
                    updated = True
                else:
                    new_sections.append(section)
            
            if not updated:
                return False
                
            with open(self.queue_path, 'w') as f:
                f.write("\n\n".join(new_sections))
            return True
        except Exception as e:
            print(f"Error updating queue: {e}")
            return False

    def delete_queue(self, queue_name: str) -> bool:
        """Delete a queue configuration"""
        try:
            if not os.path.exists(self.queue_path):
                return False

            with open(self.queue_path, 'r') as f:
                content = f.read()
            
            queue_sections = content.split("\n\n")
            new_sections = [section for section in queue_sections if not section.startswith(f"[{queue_name}]")]
            
            with open(self.queue_path, 'w') as f:
                f.write("\n\n".join(new_sections))
            return True
        except Exception as e:
            print(f"Error deleting queue: {e}")
            return False

    def list_queues(
        self,
        name_filter: Optional[str] = None,
        context_filter: Optional[str] = None,
        strategy_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> QueueListResponse:
        """List all queue configurations with filtering and pagination"""
        try:
            if not os.path.exists(self.queue_path):
                return QueueListResponse(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    total_pages=0
                )

            with open(self.queue_path, 'r') as f:
                content = f.read()
            
            queue_sections = content.split("\n\n")
            queues = []
            
            for section in queue_sections:
                if section.strip() and section.startswith('['):
                    queue = self._parse_queue_section(section)
                    if queue:
                        # Apply filters
                        if name_filter and name_filter.lower() not in queue.name.lower():
                            continue
                        if context_filter and context_filter.lower() not in queue.context.lower():
                            continue
                        if strategy_filter and strategy_filter.lower() != queue.strategy.lower():
                            continue
                        queues.append(queue)
            
            # Calculate pagination
            total = len(queues)
            total_pages = (total + page_size - 1) // page_size
            
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_queues = queues[start_idx:end_idx]
            
            return QueueListResponse(
                items=paginated_queues,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        except Exception as e:
            print(f"Error listing queues: {e}")
            return QueueListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            ) 