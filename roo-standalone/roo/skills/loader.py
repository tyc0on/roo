"""
Skill Loader

Parses skill definitions from markdown files.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import re
import frontmatter


@dataclass
class Skill:
    """A skill definition loaded from a markdown file."""
    name: str
    description: str
    content: str  # Raw markdown body with actions
    trigger_keywords: List[str] = field(default_factory=list)
    requires_auth: bool = False
    parameters: List[dict] = field(default_factory=list)
    
    def __repr__(self):
        return f"Skill(name='{self.name}')"


def load_skills(skills_dir: Path) -> List[Skill]:
    """
    Load all skill definitions from markdown files.
    
    Args:
        skills_dir: Directory containing *.md skill files
    
    Returns:
        List of Skill objects
    """
    skills = []
    
    if not skills_dir.exists():
        print(f"⚠️  Skills directory not found: {skills_dir}")
        return skills
    
    for md_file in skills_dir.glob("*.md"):
        try:
            skill = load_skill_file(md_file)
            if skill:
                skills.append(skill)
                print(f"   ✅ Loaded skill: {skill.name}")
        except Exception as e:
            print(f"   ❌ Failed to load {md_file.name}: {e}")
    
    return skills


def load_skill_file(file_path: Path) -> Optional[Skill]:
    """Load a single skill from a markdown file."""
    post = frontmatter.load(file_path)
    
    name = post.metadata.get("name")
    if not name:
        print(f"   ⚠️  Skipping {file_path.name}: missing 'name' in frontmatter")
        return None
    
    # Try to extract parameters from markdown if not in frontmatter
    parameters = post.metadata.get("parameters", [])
    if not parameters and post.content:
        parameters = _extract_parameters_from_markdown(post.content)

    return Skill(
        name=name,
        description=post.metadata.get("description", ""),
        content=post.content,
        trigger_keywords=post.metadata.get("trigger_keywords", []),
        requires_auth=post.metadata.get("requires_auth", False),
        parameters=parameters
    )


def _extract_parameters_from_markdown(content: str) -> List[dict]:
    """
    Extract parameters from '## Parameters' section in markdown.
    
    Expected format:
    - **name**: description
    """
    parameters = []
    
    # improved regex to capture parameter section
    # looks for ## Parameters, then captures lines until next heading or end
    match = re.search(r'##\s+Parameters\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return parameters
        
    section = match.group(1)
    
    # Parse bullet points
    for line in section.split('\n'):
        line = line.strip()
        if not line.startswith(('-', '*')):
            continue
            
        # Extract name and description
        # - **query**: The expertise...
        param_match = re.search(r'[-*]\s+\*\*([a-zA-Z0-9_]+)\*\*:\s*(.*)', line)
        if param_match:
            name, desc = param_match.groups()
            parameters.append({
                "name": name,
                "description": desc.strip(),
                "required": "(required)" in desc.lower(),
                "default": _extract_default(desc)
            })
            
    return parameters


def _extract_default(desc: str) -> Optional[str]:
    """Extract default value from description."""
    match = re.search(r'\(default:\s*(.*?)\)', desc, re.IGNORECASE)
    return match.group(1) if match else None
