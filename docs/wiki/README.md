# Wiki Documentation

This directory contains the source files for the mcp-ssh-orchestrator GitHub wiki. These files are automatically synchronized to the GitHub wiki repository via GitHub Actions.

## Directory Structure

```bash
docs/wiki/
├── Home.md                    # Landing page
├── _Sidebar.md                # Navigation structure
├── 01-MCP-Overview.md         # MCP protocol overview
├── 02-Risks.md                # Security risks and threats
├── 03-Design-Goals.md         # Project philosophy
├── 04-Architecture.md         # System architecture
├── 05-Security-Model.md       # Security architecture
├── 06-Configuration.md       # Configuration overview
├── 06.1-servers.yml.md        # Host inventory configuration
├── 06.2-credentials.yml.md   # SSH authentication configuration
├── 06.3-policy.yml.md        # Security policy configuration
├── 07-Tools-Reference.md     # Complete MCP tools documentation
├── 08-Usage-Cookbook.md      # Practical usage examples
├── 09-Deployment.md          # Production deployment guide
├── 10-Integrations.md        # MCP client integrations
├── 11-Observability-Audit.md  # Monitoring and compliance
├── 12-Troubleshooting.md     # Common issues and solutions
├── 13-Contributing.md        # Development workflow
├── 14-FAQ.md                 # Frequently asked questions
├── 15-Glossary.md            # Terms and definitions
└── assets/                   # Images, diagrams, examples
    ├── diagrams/
    └── examples/
        ├── policy-examples/
        └── docker-configs/
```

## Synchronization Process

### Automatic Sync

The wiki is automatically synchronized when changes are pushed to the `main` branch:

1. **GitHub Actions Workflow** (`.github/workflows/sync-wiki.yml`) triggers on push to `main`
2. **Wiki Repository** is cloned from `https://github.com/samerfarida/mcp-ssh-orchestrator.wiki.git`
3. **Content Sync** copies all files from `docs/wiki/` to the wiki repository
4. **Validation** checks markdown syntax and validates links
5. **Commit & Push** updates the wiki repository with changes

### Manual Sync

You can also trigger the sync manually:

1. Go to **Actions** tab in GitHub
2. Select **Sync Wiki Documentation** workflow
3. Click **Run workflow**
4. Select the branch (usually `main`)
5. Click **Run workflow**

### Sync Requirements

- **Write access** to the main repository
- **Wiki enabled** for the repository
- **GitHub Actions** enabled for the repository

## Editing Workflow

### Making Changes

1. **Edit files** in `docs/wiki/` directory
2. **Test locally** using markdown preview
3. **Commit changes** to your branch
4. **Create pull request** for review
5. **Merge to main** triggers automatic sync

### File Guidelines

- **Use Markdown** syntax for all content
- **Include diagrams** using Mermaid syntax directly in markdown with ` ```mermaid ` code blocks
- **Test links** before committing
- **Follow naming conventions** for consistency
- **Add cross-references** between related sections

### Content Standards

- **Purpose statement** at the top of each page
- **Clear section headers** with consistent formatting
- **Code examples** with proper syntax highlighting
- **Security context** for all technical examples
- **Cross-references** to related sections

## Validation

### Automatic Validation

The sync process includes automatic validation:

- **YAML syntax** checking for configuration examples
- **Markdown linting** for formatting consistency
- **Link checking** for broken references
- **Image validation** for missing assets

### Manual Validation

Before committing, validate your changes:

# Check markdown syntax

python -c "import yaml; yaml.safe_load(open('docs/wiki/06.3-policy.yml.md'))"

# Validate links (if link checker is installed)

markdown-link-check docs/wiki/Home.md

# Check for broken references

grep -r "\[.*\](" docs/wiki/ | grep -v "http"

```bash

## Troubleshooting

### Sync Issues

### Wiki not updating:

1. Check GitHub Actions workflow status
2. Verify wiki repository exists and is accessible
3. Check for YAML syntax errors in configuration examples
4. Review workflow logs for specific error messages

### Broken links:

1. Use relative paths for internal wiki links
2. Test links before committing
3. Check that referenced pages exist
4. Use absolute URLs for external links

### Missing images:

1. Ensure images are in `docs/wiki/assets/` directory
2. Use relative paths in markdown: `![alt](assets/image.png)`
3. Check file permissions and case sensitivity

### Content Issues

### Markdown rendering:

1. Use standard Markdown syntax
2. Avoid complex HTML in markdown files
3. Test rendering in GitHub preview
4. Check for special characters that need escaping

### Mermaid diagrams:

1. Embed diagrams directly in markdown using ` ```mermaid ` code blocks
2. Test diagram syntax with Mermaid preview tools
3. Keep diagrams close to the content they illustrate

## Contributing

### Adding New Content

1. **Create new markdown file** in appropriate location
2. **Update `_Sidebar.md`** to include new page
3. **Add cross-references** from related pages
4. **Test locally** before committing
5. **Submit pull request** for review

### Updating Existing Content

1. **Edit existing markdown file**
2. **Maintain consistent formatting**
3. **Update cross-references** if needed
4. **Test changes** before committing
5. **Submit pull request** for review

### Content Review Process

1. **Technical accuracy** - Verify all technical details
2. **Security context** - Ensure security implications are clear
3. **Consistency** - Check formatting and style consistency
4. **Completeness** - Verify all examples are complete and runnable
5. **Cross-references** - Ensure links work and are relevant

## Maintenance

### Regular Tasks

- **Review and update** content quarterly
- **Check for broken links** monthly
- **Update examples** when configuration changes
- **Add new sections** as features are added
- **Archive outdated content** appropriately

### Version Control

- **Tag releases** with corresponding documentation versions
- **Maintain changelog** for significant documentation changes
- **Archive old versions** when major updates occur
- **Document breaking changes** clearly

## Support

For questions about the wiki documentation:

- **Open an issue** in the main repository
- **Create a discussion** for general questions
- **Submit a pull request** for documentation improvements
- **Contact maintainers** for urgent issues

## License

This documentation is licensed under the same terms as the main project (Apache 2.0). See the main repository LICENSE file for details.
