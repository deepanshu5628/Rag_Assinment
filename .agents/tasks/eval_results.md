# Evaluation results - Vectra KB RAG assistant

**Overall: 8/8 questions passed all graded dimensions.**

## Summary table

| # | Retrieved | Abstain | Citation | Safe | Pass | Citations | Abstained |
|---|-----------|---------|----------|------|------|-----------|-----------|
| 1 | PASS | PASS | PASS | PASS | PASS | ['KB-001'] | False |
| 2 | PASS | PASS | PASS | PASS | PASS | ['KB-007'] | False |
| 3 | PASS | PASS | PASS | PASS | PASS | ['KB-003'] | False |
| 4 | PASS | PASS | PASS | PASS | PASS | [] | True |
| 5 | PASS | PASS | PASS | PASS | PASS | ['KB-004'] | False |
| 6 | PASS | PASS | PASS | PASS | PASS | ['KB-007'] | False |
| 7 | PASS | PASS | PASS | PASS | PASS | ['KB-007'] | False |
| 8 | PASS | PASS | PASS | PASS | PASS | [] | True |

## Per-question detail

### Q1
- Question: My account is locked, what do I do?
- Abstained: False  |  Citations: ['KB-001']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: Your account will unlock automatically after 30 minutes. If you need immediate access, you can try resetting your password using the self-service option at https://reset.vectralogistics.example. If that fails, please raise a ticket with the category "Access" for further assistance.

### Q2
- Question: What is the VPN server address I should use from home?
- Abstained: False  |  Citations: ['KB-007']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: The VPN server address you should use from home is **zt-gw.vectralogistics.example**. This address is selected automatically after you sign in with ZenTunnel.

### Q3
- Question: What is the resolution target for a P2 ticket?
- Abstained: False  |  Citations: ['KB-003']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: The resolution target for a P2 ticket is 8 hours.

### Q4
- Question: How do I get a parking pass for the Gurugram office?
- Abstained: True  |  Citations: []
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: I don't have information about that in the Vectra IT knowledge base, so I can't answer reliably. Please raise a ticket with the service desk and the right team will help you.

### Q5
- Question: Hi, I'm Anand Sharma (a***@vectralogistics.example, [PHONE ***10]). How do I set up my company email on my iPhone's built-in Mail app?
- Abstained: False  |  Citations: ['KB-004']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: Company mail on phones is supported only in the Outlook mobile app with Intune enrolment; native mail apps are blocked. Therefore, you cannot set up your company email on your iPhone's built-in Mail app.

### Q6
- Question: Can I use ZenTunnel VPN on my Linux laptop?
- Abstained: False  |  Citations: ['KB-007']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: Unsupported operating systems (including Linux) are not covered by this guide; please raise a ticket for Network Ops to assess.

### Q7
- Question: ZenTunnel shows error ZT-401. How do I fix it?
- Abstained: False  |  Citations: ['KB-007']
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: To fix the ZT-401 error, sign out of ZenTunnel and then sign in again. If the issue persists, check that your device is enrolled in the Company Portal.

### Q8
- Question: My work laptop is really slow. How can I speed it up?
- Abstained: True  |  Citations: []
- Dimensions: {'retrieved': True, 'abstain': True, 'citation': True, 'safe': True}
- Answer: I don't have information about that in the Vectra IT knowledge base, so I can't answer reliably. Please raise a ticket with the service desk and the right team will help you.
