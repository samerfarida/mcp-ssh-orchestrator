# 16. Glossary

**Purpose:** Define key terms, concepts, and acronyms used throughout MCP SSH Orchestrator documentation.

## Overview

This glossary provides definitions for technical terms, concepts, and acronyms used in MCP SSH Orchestrator documentation. Terms are organized alphabetically for easy reference.

## A

**Access Control**
- **Definition**: Security mechanism that controls who can access what resources and under what conditions
- **Context**: MCP SSH Orchestrator implements policy-based access control for SSH command execution

**Agent**
- **Definition**: An AI system that can perceive its environment and take actions to achieve goals
- **Context**: AI agents interact with mcp-ssh-orchestrator through the MCP protocol to execute SSH commands

**Alias**
- **Definition**: A human-readable name for a host in the servers.yml configuration
- **Context**: Used to reference hosts instead of IP addresses (e.g., "web1" instead of "10.0.0.11")

**Audit Log**
- **Definition**: A chronological record of events and activities for security oversight
- **Context**: MCP SSH Orchestrator provides structured JSON audit logs for every command execution

**Authentication**
- **Definition**: The process of verifying the identity of a user or system
- **Context**: SSH authentication using public/private key pairs or passwords

## B

**Blocklist**
- **Definition**: A list of items (IPs, commands, hosts) that are explicitly denied access
- **Context**: Network blocklists prevent connections to unauthorized IP addresses

## C

**CIDR**
- **Definition**: Classless Inter-Domain Routing, a method for allocating IP addresses and routing
- **Context**: Used for network filtering (e.g., "10.0.0.0/8" allows all 10.x.x.x addresses)

**Command Injection**
- **Definition**: A security vulnerability where malicious commands are injected into legitimate commands
- **Context**: MCP SSH Orchestrator prevents command injection through policy enforcement and input validation

**Compliance**
- **Definition**: Adherence to regulatory or organizational policies and standards
- **Context**: MCP SSH Orchestrator provides security features that can assist with internal governance. Certification against external standards is the responsibility of the deploying organization.

**Container**
- **Definition**: A lightweight, portable unit of software that packages code and dependencies
- **Context**: MCP SSH Orchestrator is distributed as a Docker container for easy deployment

## D

**Defense in Depth**
- **Definition**: A security strategy that implements multiple layers of security controls
- **Context**: MCP SSH Orchestrator implements policy enforcement, network filtering, audit logging, and container security

**Docker**
- **Definition**: A platform for developing, shipping, and running applications in containers
- **Context**: MCP SSH Orchestrator uses Docker for packaging and deployment

**Dry Run**
- **Definition**: A test execution that simulates a command without actually executing it
- **Context**: The ssh_plan tool performs dry runs to test policy rules before execution

## E

**Ed25519**
- **Definition**: A public-key signature algorithm that is fast, secure, and compact
- **Context**: Recommended SSH key type for mcp-ssh-orchestrator deployments

**Environment Variable**
- **Definition**: A dynamic value that can affect how processes behave
- **Context**: Used for configuration and secret management in mcp-ssh-orchestrator

## F

**Fleet**
- **Definition**: A collection of servers or hosts managed as a group
- **Context**: MCP SSH Orchestrator manages SSH access to a fleet of servers

**Firewall**
- **Definition**: A network security device that monitors and controls network traffic
- **Context**: MCP SSH Orchestrator implements network filtering similar to firewall rules

## G

**GitHub Actions**
- **Definition**: A CI/CD platform that automates software workflows
- **Context**: Used for automated testing, building, and deployment of mcp-ssh-orchestrator

**GitHub Wiki**
- **Definition**: A documentation platform for GitHub repositories
- **Context**: MCP SSH Orchestrator documentation is maintained in the GitHub wiki

## H

**Host Key**
- **Definition**: A cryptographic key used to verify the identity of an SSH server
- **Context**: MCP SSH Orchestrator verifies host keys to prevent man-in-the-middle attacks

**Hostname**
- **Definition**: A human-readable name for a network device
- **Context**: Used in servers.yml to specify the target host for SSH connections

## I

**IP Address**
- **Definition**: A numerical label assigned to each device connected to a network
- **Context**: Used to identify target hosts in servers.yml configuration

**Incident Response**
- **Definition**: The process of responding to security incidents and breaches
- **Context**: MCP SSH Orchestrator provides audit logs and monitoring for incident response

## J

**JSON-RPC**
- **Definition**: A remote procedure call protocol encoded in JSON
- **Context**: MCP uses JSON-RPC for communication between clients and servers

## K

**Key Pair**
- **Definition**: A set of two cryptographic keys (public and private) used for encryption
- **Context**: SSH key pairs are used for authentication in mcp-ssh-orchestrator

**Known Hosts**
- **Definition**: A file containing the public keys of SSH servers
- **Context**: MCP SSH Orchestrator uses known_hosts for host key verification

## L

**LLM**
- **Definition**: Large Language Model, an AI system trained on vast amounts of text data
- **Context**: LLMs interact with mcp-ssh-orchestrator through MCP clients

**Load Balancer**
- **Definition**: A device that distributes network traffic across multiple servers
- **Context**: Not currently implemented in MCP SSH Orchestrator. The tool is designed for one container per MCP client, with scaling handled at the client level.

## M

**MCP**
- **Definition**: Model Context Protocol, a standardized interface for AI agents to interact with external tools
- **Context**: MCP SSH Orchestrator implements the MCP protocol for AI agent integration

**Mermaid**
- **Definition**: A markdown-like syntax for generating diagrams
- **Context**: Used in mcp-ssh-orchestrator documentation for architecture diagrams

**Microservices**
- **Definition**: An architectural approach where applications are built as a collection of loosely coupled services
- **Context**: Future mcp-ssh-orchestrator versions may adopt microservices architecture

## N

**Network Segmentation**
- **Definition**: The practice of dividing a network into smaller, isolated segments
- **Context**: MCP SSH Orchestrator supports network filtering for segmentation

**Non-root**
- **Definition**: Running processes with limited privileges instead of administrator/root privileges
- **Context**: MCP SSH Orchestrator containers run as non-root user for security

## O

**OWASP**
- **Definition**: Open Web Application Security Project, a nonprofit foundation focused on software security
- **Context**: MCP SSH Orchestrator addresses OWASP Top 10 for LLMs security risks

**Orchestrator**
- **Definition**: A system that manages and coordinates multiple components or services
- **Context**: MCP SSH Orchestrator orchestrates SSH access across a fleet of servers

## P

**Policy**
- **Definition**: A set of rules that govern behavior or access control
- **Context**: MCP SSH Orchestrator uses policies to control SSH command execution

**Policy Engine**
- **Definition**: A system that evaluates policies and makes access control decisions
- **Context**: The core component of mcp-ssh-orchestrator that enforces security policies

**Prompt Injection**
- **Definition**: A security vulnerability where malicious input manipulates AI system behavior
- **Context**: MCP SSH Orchestrator prevents prompt injection through policy enforcement

**Privilege Escalation**
- **Definition**: The act of exploiting a bug or design flaw to gain elevated access
- **Context**: MCP SSH Orchestrator prevents privilege escalation through command restrictions

## Q

**QoS**
- **Definition**: Quality of Service, the ability to provide different priority levels for different applications
- **Context**: MCP SSH Orchestrator implements QoS through resource limits and rate limiting

## R

**Rate Limiting**
- **Definition**: A technique to control the rate of requests or operations
- **Context**: MCP SSH Orchestrator implements rate limiting to prevent abuse

**RBAC**
- **Definition**: Role-Based Access Control, a method of restricting access based on user roles
- **Context**: Future mcp-ssh-orchestrator versions will support RBAC

**Read-only**
- **Definition**: A filesystem or volume that can only be read from, not written to
- **Context**: MCP SSH Orchestrator containers use read-only filesystems for security

## S

**SSH**
- **Definition**: Secure Shell, a cryptographic network protocol for secure remote access
- **Context**: MCP SSH Orchestrator manages SSH access to remote servers

**SSH Key**
- **Definition**: A cryptographic key used for SSH authentication
- **Context**: MCP SSH Orchestrator uses SSH keys for secure authentication

**Secret**
- **Definition**: Sensitive information such as passwords, keys, or tokens
- **Context**: MCP SSH Orchestrator manages secrets through Docker secrets or environment variables

**stdio**
- **Definition**: Standard input/output, a communication method using standard streams
- **Context**: MCP uses stdio transport for communication between clients and servers

## T

**Tag**
- **Definition**: A label or identifier used to categorize or group items
- **Context**: Hosts in mcp-ssh-orchestrator are tagged for policy grouping (e.g., "production", "web")

**TLS**
- **Definition**: Transport Layer Security, a cryptographic protocol for secure communication
- **Context**: MCP SSH Orchestrator may use TLS for secure communication in future versions

**Timeout**
- **Definition**: A maximum time limit for an operation before it is terminated
- **Context**: MCP SSH Orchestrator implements timeouts to prevent hanging commands

## U

**Uptime**
- **Definition**: The amount of time a system has been running without interruption
- **Context**: MCP SSH Orchestrator monitors uptime and system health

**User**
- **Definition**: An individual or system that interacts with mcp-ssh-orchestrator
- **Context**: Users can be human operators or AI agents

## V

**Vulnerability**
- **Definition**: A weakness in a system that can be exploited to cause harm
- **Context**: MCP SSH Orchestrator addresses common SSH and MCP vulnerabilities

## W

**Webhook**
- **Definition**: A way for an application to provide real-time information to other applications
- **Context**: Future mcp-ssh-orchestrator versions may support webhooks for notifications

**Wiki**
- **Definition**: A collaborative website that allows users to create and edit content
- **Context**: MCP SSH Orchestrator documentation is maintained in the GitHub wiki

## X

**XSS**
- **Definition**: Cross-Site Scripting, a security vulnerability where malicious scripts are injected into web pages
- **Context**: Not directly applicable to mcp-ssh-orchestrator, but related to web security

## Y

**YAML**
- **Definition**: YAML Ain't Markup Language, a human-readable data serialization format
- **Context**: MCP SSH Orchestrator configuration files use YAML format

## Z

**Zero Trust**
- **Definition**: A security model that assumes no implicit trust and verifies every request
- **Context**: Future mcp-ssh-orchestrator versions will implement zero trust architecture

**Zone**
- **Definition**: A logical grouping of network resources
- **Context**: MCP SSH Orchestrator supports network zones for security segmentation

## Acronyms

**API**: Application Programming Interface
**CI/CD**: Continuous Integration/Continuous Deployment
**CLI**: Command Line Interface
**CPU**: Central Processing Unit
**DNS**: Domain Name System
**FTP**: File Transfer Protocol
**HTTP**: Hypertext Transfer Protocol
**HTTPS**: HTTP Secure
**IAM**: Identity and Access Management
**ID**: Identifier
**IP**: Internet Protocol
**JSON**: JavaScript Object Notation
**LDAP**: Lightweight Directory Access Protocol
**MAC**: Media Access Control
**NAT**: Network Address Translation
**OS**: Operating System
**RAM**: Random Access Memory
**REST**: Representational State Transfer
**SDK**: Software Development Kit
**SIEM**: Security Information and Event Management
**SOAR**: Security Orchestration, Automation and Response
**SSH**: Secure Shell
**SSL**: Secure Sockets Layer
**TCP**: Transmission Control Protocol
**UDP**: User Datagram Protocol
**UI**: User Interface
**URL**: Uniform Resource Locator
**UUID**: Universally Unique Identifier
**VPN**: Virtual Private Network
**WAF**: Web Application Firewall
**XML**: eXtensible Markup Language

## Next Steps

- **[FAQ](14-FAQ)** - Common questions and answers
- **[Troubleshooting](12-Troubleshooting)** - Problem-solving guide
- **[Security Model](05-Security-Model)** - Security architecture details
- **[Architecture](04-Architecture)** - System design and components
