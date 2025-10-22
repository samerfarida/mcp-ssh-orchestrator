# Policy Engine Flowchart

This flowchart visualizes the policy engine logic in mcp-ssh-orchestrator.

## Command Execution Flow

```mermaid
flowchart TD
    Start([ssh_run called]) --> ValidateInput{Valid alias<br/>and command?}
    ValidateInput -->|No| ErrorInput[Return: Error]
    ValidateInput -->|Yes| CheckDenySubstrings[Check deny_substrings<br/>from limits]
    
    CheckDenySubstrings --> HasDeniedSubstring{Command contains<br/>denied substring?}
    HasDeniedSubstring -->|Yes| DenySubstring[Log decision: denied<br/>Return: Denied by policy]
    HasDeniedSubstring -->|No| CheckRules[Iterate through policy rules]
    
    CheckRules --> MatchRule{Find matching rule?<br/>Check: aliases, tags, commands}
    MatchRule -->|No match found| DenyDefault[matched = None<br/>Log decision: denied<br/>Return: Denied by policy]
    MatchRule -->|Match found| CheckAction{Action type?}
    
    CheckAction -->|deny| DenyRule[Log decision: denied<br/>Return: Denied by policy]
    CheckAction -->|allow| AllowPolicy[Log decision: allowed<br/>Policy check passed]
    
    AllowPolicy --> NetworkPrecheck[DNS resolution<br/>Resolve hostname to IPs]
    NetworkPrecheck --> HasIPs{IPs resolved?}
    HasIPs -->|No| DenyDNS[Return: Denied by network<br/>DNS resolution failed]
    HasIPs -->|Yes| CheckIPAllowlist[Check each IP against<br/>network policy]
    
    CheckIPAllowlist --> CheckBlockIP{IP in block_ips?}
    CheckBlockIP -->|Yes| DenyBlockIP[Return: Denied by network<br/>IP blocked]
    CheckBlockIP -->|No| CheckBlockCIDR{IP in block_cidrs?}
    
    CheckBlockCIDR -->|Yes| DenyBlockCIDR[Return: Denied by network<br/>CIDR blocked]
    CheckBlockCIDR -->|No| HasAllowLists{Allow lists configured?}
    
    HasAllowLists -->|Yes| CheckAllowIP{IP in allow_ips<br/>or allow_cidrs?}
    CheckAllowIP -->|No| DenyNotAllowed[Return: Denied by network<br/>IP not in allowlist]
    CheckAllowIP -->|Yes| NetworkOK[Network precheck passed]
    HasAllowLists -->|No| NetworkOK
    
    NetworkOK --> CreateTask[Create task with cancel event]
    CreateTask --> GetLimits[Get effective limits:<br/>max_seconds, max_output_bytes<br/>host_key_auto_add, require_known_host]
    GetLimits --> CreateClient[Create SSH client<br/>with credentials and limits]
    CreateClient --> ExecuteCommand[Execute command<br/>with streaming, timeout, cancel]
    
    ExecuteCommand --> PostConnectCheck[Post-connect enforcement<br/>Check actual peer IP]
    PostConnectCheck --> PeerIPAllowed{Peer IP allowed<br/>by network policy?}
    PeerIPAllowed -->|No| DenyPeerIP[Log audit<br/>Return: Denied by network<br/>peer IP not allowed]
    PeerIPAllowed -->|Yes| LogAudit[Log audit:<br/>exit_code, duration, bytes, etc.]
    
    LogAudit --> ReturnResult[Return execution result:<br/>output, exit_code, duration, etc.]
    ReturnResult --> End([End])
    
    DenySubstring --> End
    DenyDefault --> End
    DenyRule --> End
    DenyDNS --> End
    DenyBlockIP --> End
    DenyBlockCIDR --> End
    DenyNotAllowed --> End
    DenyPeerIP --> End
    ErrorInput --> End
    
    style Start fill:#90EE90
    style End fill:#FFB6C1
    style DenySubstring fill:#FFA07A
    style DenyDefault fill:#FFA07A
    style DenyRule fill:#FFA07A
    style DenyDNS fill:#FFA07A
    style DenyBlockIP fill:#FFA07A
    style DenyBlockCIDR fill:#FFA07A
    style DenyNotAllowed fill:#FFA07A
    style DenyPeerIP fill:#FFA07A
    style ErrorInput fill:#FFA07A
    style AllowPolicy fill:#98FB98
    style NetworkOK fill:#98FB98
    style ReturnResult fill:#87CEEB
```

## Limits Resolution Flow

```mermaid
flowchart TD
    StartLimits([Get limits for alias/tags]) --> DefaultLimits[Start with default_limits:<br/>max_seconds: 60<br/>max_output_bytes: 1MB<br/>host_key_auto_add: false<br/>require_known_host: true<br/>deny_substrings: extensive list]
    
    DefaultLimits --> GlobalLimits[Apply global policy.limits]
    GlobalLimits --> AliasOverride[Apply alias-specific overrides<br/>from policy.overrides.aliases]
    AliasOverride --> TagOverride[Apply tag-specific overrides<br/>from policy.overrides.tags<br/>Only if not set by alias]
    
    TagOverride --> ReturnLimits[Return effective limits]
    ReturnLimits --> EndLimits([End])
    
    style StartLimits fill:#90EE90
    style EndLimits fill:#FFB6C1
    style ReturnLimits fill:#87CEEB
```

## Rule Matching Logic

```mermaid
flowchart TD
    StartMatch([Match command against rules]) --> IterateRules[For each rule in policy.rules]
    
    IterateRules --> CheckAliases{aliases specified?}
    CheckAliases -->|No| AliasOK[alias_ok = true]
    CheckAliases -->|Yes| MatchAlias{Alias matches<br/>any pattern?}
    MatchAlias -->|Yes| AliasOK
    MatchAlias -->|No| NextRule1[Skip to next rule]
    
    AliasOK --> CheckTags{tags specified?}
    CheckTags -->|No or empty| TagsOK[tags_ok = true]
    CheckTags -->|Yes| MatchTag{Any host tag matches<br/>any pattern?}
    MatchTag -->|Yes| TagsOK
    MatchTag -->|No| NextRule2[Skip to next rule]
    
    TagsOK --> CheckCommands{commands specified?}
    CheckCommands -->|No or empty| NextRule3[Skip to next rule<br/>cmd_ok = false]
    CheckCommands -->|Yes| MatchCommand{Command matches<br/>any pattern?}
    MatchCommand -->|Yes| RuleMatched[Rule matched!<br/>Return action: allow/deny]
    MatchCommand -->|No| NextRule4[Skip to next rule]
    
    NextRule1 --> MoreRules1{More rules?}
    NextRule2 --> MoreRules1
    NextRule3 --> MoreRules1
    NextRule4 --> MoreRules1
    
    MoreRules1 -->|Yes| IterateRules
    MoreRules1 -->|No| NoMatch[No match found<br/>Return: deny default]
    
    RuleMatched --> EndMatch([End])
    NoMatch --> EndMatch
    
    style StartMatch fill:#90EE90
    style EndMatch fill:#FFB6C1
    style RuleMatched fill:#98FB98
    style NoMatch fill:#FFA07A
```

## IP Network Policy Check

```mermaid
flowchart TD
    StartIP([is_ip_allowed called]) --> CheckBlockIPs{IP in network.block_ips?}
    
    CheckBlockIPs -->|Yes| DenyIP[Return: false<br/>IP blocked]
    CheckBlockIPs -->|No| CheckBlockCIDRs{IP in network.block_cidrs?}
    
    CheckBlockCIDRs -->|Yes| DenyCIDR[Return: false<br/>CIDR blocked]
    CheckBlockCIDRs -->|No| HasAllowListsIP{network.allow_ips or<br/>network.allow_cidrs configured?}
    
    HasAllowListsIP -->|No| AllowByDefault[Return: true<br/>No allowlists = allow all<br/>blocks already applied]
    HasAllowListsIP -->|Yes| CheckAllowIPsIP{IP in network.allow_ips?}
    
    CheckAllowIPsIP -->|Yes| AllowIP[Return: true<br/>IP explicitly allowed]
    CheckAllowIPsIP -->|No| CheckAllowCIDRsIP{IP in network.allow_cidrs?}
    
    CheckAllowCIDRsIP -->|Yes| AllowCIDR[Return: true<br/>CIDR match allowed]
    CheckAllowCIDRsIP -->|No| DenyNotInAllowlist[Return: false<br/>Not in allowlist]
    
    DenyIP --> EndIP([End])
    DenyCIDR --> EndIP
    AllowByDefault --> EndIP
    AllowIP --> EndIP
    AllowCIDR --> EndIP
    DenyNotInAllowlist --> EndIP
    
    style StartIP fill:#90EE90
    style EndIP fill:#FFB6C1
    style AllowByDefault fill:#98FB98
    style AllowIP fill:#98FB98
    style AllowCIDR fill:#98FB98
    style DenyIP fill:#FFA07A
    style DenyCIDR fill:#FFA07A
    style DenyNotInAllowlist fill:#FFA07A
```

## Key Principles

1. **Deny by default**: Commands must match an "allow" rule to execute
2. **Defense in depth**: Multiple layers of checks (deny_substrings → rules → network)
3. **Fail closed**: Any error in validation results in denial
4. **Pre and post checks**: Network policy enforced before and after connection
5. **Hierarchical limits**: Default → Global → Alias → Tags (with precedence rules)
6. **Audit logging**: All decisions and executions are logged with timestamps and hashes

