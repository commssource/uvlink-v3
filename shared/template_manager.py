import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound, TemplateSyntaxError
from jinja2.exceptions import UndefinedError
import aiofiles
import asyncio


class UnifiedTemplateManager:
    """Unified template manager for PJSIP and Queue configurations"""
    
    def __init__(self, template_dirs: Union[str, Path, List[Union[str, Path]]] = None):
        if template_dirs is None:
            template_dirs = ["templates"]
        elif isinstance(template_dirs, (str, Path)):
            template_dirs = [template_dirs]
        
        self.template_dirs = [Path(td) for td in template_dirs]
        self.logger = logging.getLogger(f"{__name__}.UnifiedTemplateManager")
        
        # Ensure template directories exist
        for template_dir in self.template_dirs:
            template_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = self._setup_jinja_environment()
        
        # Template cache for performance
        self._template_cache = {}
    
    def _setup_jinja_environment(self) -> Environment:
        """Setup Jinja2 environment with multiple template directories"""
        from jinja2 import ChoiceLoader
        
        # Create loaders for all template directories
        loaders = [FileSystemLoader(str(td)) for td in self.template_dirs]
        loader = ChoiceLoader(loaders)
        
        env = Environment(
            loader=loader,
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            newline_sequence='\n'
        )
        
        # Add basic filters
        env.filters.update({
            'bool_to_yesno': self._bool_to_yesno,
        })
        
        return env
    
    def _bool_to_yesno(self, value: Any) -> str:
        """Convert boolean to yes/no string"""
        if isinstance(value, bool):
            return 'yes' if value else 'no'
        if isinstance(value, str):
            return 'yes' if value.lower() in ('true', '1', 'yes', 'on') else 'no'
        return 'no'
    
    async def render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render a template with the given variables"""
        try:
            # Ensure template has .j2 extension
            if not template_name.endswith('.j2'):
                template_name += '.j2'
            
            # Get template
            template = self.env.get_template(template_name)
            
            # Render template
            content = await self._render_async(template, variables)
            
            self.logger.debug(f"Successfully rendered template '{template_name}'")
            return content.strip()
            
        except TemplateNotFound as e:
            error_msg = f"Template not found: {template_name}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Template rendering error for '{template_name}': {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    async def _render_async(self, template, variables: Dict[str, Any]) -> str:
        """Render template asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, template.render, variables)
    
    async def list_templates(self) -> List[str]:
        """List available templates from all directories"""
        templates = set()
        try:
            for template_dir in self.template_dirs:
                if template_dir.exists():
                    for template_file in template_dir.glob('**/*.j2'):
                        rel_path = template_file.relative_to(template_dir)
                        templates.add(str(rel_path.with_suffix('')))
        except Exception as e:
            self.logger.error(f"Failed to list templates: {e}")
        
        return sorted(list(templates))