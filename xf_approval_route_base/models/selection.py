M2M_POSITIVE_TERM_OPERATOR = 'in'
M2M_NEGATIVE_TERM_OPERATOR = 'not in'

M2M_TERM_OPERATORS = [
    (M2M_POSITIVE_TERM_OPERATOR, 'Contain (in)'),
    (M2M_NEGATIVE_TERM_OPERATOR, 'Do not contain (not in)'),
]

AMOUNT_TERM_LE_OPERATOR = '<='
AMOUNT_TERM_GE_OPERATOR = '>='

AMOUNT_TERM_OPERATORS = [
    (AMOUNT_TERM_LE_OPERATOR, 'Less or Equal (<=)'),
    (AMOUNT_TERM_GE_OPERATOR, 'Greater or Equal (>=)'),
]
# APPROVAL_TYPE_DEPT_MANAGER
# department_manager
# Approval Types
APPROVAL_TYPE_ONE = 'one'
APPROVAL_TYPE_ALL = 'all'
APPROVAL_TYPE_DEPT_HEAD_LOGGED_USER = 'department_head_logged_user'
APPROVAL_TYPE_DEPT_HEAD = 'department_head'
APPROVAL_TYPE_DEPT_MANAGER_LOGGED_USER = 'dept_manager_logged_user'
APPROVAL_TYPE_DEPT_REQUESTOR = 'department_requestor'
APPROVAL_TYPE_RESPONSIBLE_USER = 'responsible_user'
APPROVAL_TYPES = [
    ('one', 'At least one approver'),
    ('department_head_logged_user','Department Head of Logged in User'),
    ('department_head','Department Head'),
    ('dept_manager_logged_user','Department Manager of Logged in User'),
    ('department_requestor','Department Head of Requestor'),
    ('all', 'All approvers'),
    ('responsible_user','Responsible User')
]

# Use Approval Route
USE_APPROVAL_ROUTE_NO = 'no'
USE_APPROVAL_ROUTE_OPTIONAL = 'optional'
USE_APPROVAL_ROUTE_REQUIRED = 'required'
USE_APPROVAL_ROUTE = [
    ('no', 'No'),
    ('optional', 'Optional'),
    ('required', 'Required'),
]

# Approval States
APPROVAL_STATE_TO_APPROVE = 'to approve'
APPROVAL_STATE_PENDING = 'pending'
APPROVAL_STATE_APPROVED = 'approved'
APPROVAL_STATE_REJECTED = 'rejected'
APPROVAL_STATES = [
    ('to approve', 'To Approve'),
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]
