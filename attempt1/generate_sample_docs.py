#!/usr/bin/env python3
"""
Generate sample text documents for testing the document classification system.
Creates 100 text files with various document types and content.
"""

import random
from pathlib import Path
from datetime import datetime, timedelta
import json

# Sample data templates
ACADEMIC_TEMPLATES = [
    """
Abstract: This paper presents a novel approach to machine learning algorithms in the context of big data analytics. We demonstrate improved performance metrics through extensive experimentation.

Introduction: Machine learning has become increasingly important in modern data science applications. Our research focuses on optimizing neural network architectures for large-scale datasets.

Methodology: We employed a combination of convolutional neural networks and reinforcement learning techniques. The dataset consisted of over 1 million samples collected from various sources.

Results: Our proposed method achieved 95% accuracy, outperforming existing state-of-the-art approaches by 12%. Statistical significance was confirmed through p-value analysis.

Conclusion: This research demonstrates significant improvements in machine learning performance. Future work will explore applications in real-world scenarios.

References:
1. Smith et al. (2023) "Advanced Neural Networks"
2. Johnson (2022) "Big Data Analytics"
""",
    """
Title: Analysis of Climate Change Impacts on Agricultural Systems

Authors: Dr. Sarah Chen, Prof. Michael Roberts

Abstract: Climate change poses significant challenges to global food security. This study analyzes the impact of temperature increases on crop yields across major agricultural regions.

Keywords: climate change, agriculture, crop yields, food security

Introduction: Agricultural systems are highly sensitive to environmental changes. Rising temperatures and changing precipitation patterns affect crop productivity worldwide.

Methodology: We analyzed 50 years of agricultural data from 200 countries. Statistical models were developed to correlate climate variables with crop yield changes.

Results: Temperature increases of 2°C are projected to reduce global crop yields by 15-20%. Regional variations are significant, with tropical areas most affected.

Discussion: These findings highlight the urgent need for climate adaptation strategies in agriculture. Policy implications and recommendations are discussed.

Conclusion: Immediate action is required to mitigate climate impacts on food production systems.
"""
]

INVOICE_TEMPLATES = [
    """
INVOICE

Invoice Number: INV-2024-{num:04d}
Date: {date}
Due Date: {due_date}

Bill To:
{customer_name}
{customer_address}
{customer_city}, {customer_state} {customer_zip}
{customer_email}

From:
Tech Solutions Inc.
123 Business Ave.
San Francisco, CA 94105
contact@techsolutions.com

Item Description                    Quantity    Unit Price    Total
----------------------------------------------------------------
Software License                    {qty1}        ${price1:.2f}     ${total1:.2f}
Technical Support                    {qty2}        ${price2:.2f}     ${total2:.2f}
Cloud Services                      {qty3}        ${price3:.2f}     ${total3:.2f}

Subtotal: ${subtotal:.2f}
Tax (8.5%): ${tax:.2f}
TOTAL: ${grand_total:.2f}

Payment Terms: Net 30
Thank you for your business!
""",
    """
SERVICE INVOICE

Invoice #: {invoice_num}
Date Issued: {date}
Payment Due: {due_date}

CLIENT INFORMATION:
{client_name}
{client_company}
{client_address}
{client_phone}
{client_email}

SERVICE DETAILS:
Description: {service_desc}
Hours Worked: {hours}
Hourly Rate: ${rate:.2f}
Amount: ${amount:.2f}

EXPENSES:
Materials: ${materials:.2f}
Travel: ${travel:.2f}
Total Expenses: ${expenses:.2f}

SUMMARY:
Services: ${amount:.2f}
Expenses: ${expenses:.2f}
Subtotal: ${subtotal:.2f}
Tax (7.5%): ${tax:.2f}
TOTAL AMOUNT DUE: ${total:.2f}

Payment Method: Bank Transfer
Account #: ****1234
"""
]

CONTRACT_TEMPLATES = [
    """
SERVICE AGREEMENT

Contract ID: CT-{num:06d}
Effective Date: {date}
Parties:

CLIENT:
{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

SERVICE PROVIDER:
Digital Solutions LLC
456 Tech Boulevard
Austin, TX 78701

SERVICES:
Provider agrees to provide web development and maintenance services as outlined in Exhibit A.

TERM:
This agreement shall commence on {start_date} and continue for a period of {term_months} months.

COMPENSATION:
Client shall pay Provider ${monthly_rate:.2f} per month, payable within 15 days of invoice.

TERMINATION:
Either party may terminate this agreement with 30 days written notice.

CONFIDENTIALITY:
Both parties agree to maintain confidentiality of all proprietary information.

GOVERNING LAW:
This agreement shall be governed by the laws of the State of Texas.

SIGNATURES:
_________________________     _________________________
Client Signature                Provider Signature

Date: {date}                   Date: {date}
""",
    """
EMPLOYMENT AGREEMENT

Agreement Date: {date}
Employee ID: EMP-{num:05d}

BETWEEN:
{company_name}
{company_address}
("Company")

AND:
{employee_name}
{employee_address}
("Employee")

POSITION:
Job Title: {job_title}
Department: {department}
Start Date: {start_date}
Salary: ${salary:,.2f} per year

TERMS OF EMPLOYMENT:
1. Duties and Responsibilities
{job_description}

2. Working Hours
Monday through Friday, 9:00 AM to 5:00 PM

3. Benefits
- Health insurance
- 401(k) matching
- Paid time off: 15 days annually

4. Termination
Either party may terminate with 14 days written notice.

CONFIDENTIALITY:
Employee agrees to maintain confidentiality of all company information.

ENTIRE AGREEMENT:
This document constitutes the entire agreement between parties.

SIGNATURES:
_________________________     _________________________
Company Representative          Employee

Date: {date}                   Date: {date}
"""
]

REPORT_TEMPLATES = [
    """
QUARTERLY BUSINESS REPORT
Q{quarter} {year}

Executive Summary:
This report provides a comprehensive overview of our company's performance for Q{quarter} {year}. Key metrics show strong growth across all business segments.

Financial Highlights:
- Revenue: ${revenue:,.2f} (up {revenue_growth:.1f}% YoY)
- Net Income: ${net_income:,.2f}
- Operating Margin: {margin:.1f}%
- Customer Acquisition: {new_customers:,} new customers

Business Segment Performance:
1. Software Solutions
   Revenue: ${software_rev:,.2f}
   Growth: {software_growth:.1f}%
   Market Share: {software_share:.1f}%

2. Consulting Services
   Revenue: ${consulting_rev:,.2f}
   Growth: {consulting_growth:.1f}%
   Projects Completed: {projects_completed}

3. Support & Maintenance
   Revenue: ${support_rev:,.2f}
   Customer Satisfaction: {satisfaction:.1f}%
   Retention Rate: {retention:.1f}%

Operational Metrics:
- Employee Count: {employees:,}
- Product Launches: {product_launches}
- R&D Investment: ${rd_investment:,.2f}

Outlook:
We project continued growth in Q{next_quarter} with expected revenue of ${projected_revenue:,.2f}.

Prepared by: {author}
Date: {date}
""",
    """
ANNUAL SAFETY REPORT
{year}

Safety Performance Overview:
This report summarizes safety incidents and prevention measures for the calendar year {year}.

Incident Statistics:
- Total Incidents: {total_incidents}
- Lost Time Injuries: {lost_time_injuries}
- Near Misses: {near_misses}
- First Aid Cases: {first_aid_cases}
- Recordable Incident Rate: {rir:.2f}

Incident Breakdown by Type:
1. Slips, Trips, Falls: {slips_incidents}
2. Equipment Related: {equipment_incidents}
3. Ergonomic: {ergonomic_incidents}
4. Chemical Exposure: {chemical_incidents}

Safety Initiatives:
- Training Sessions Conducted: {training_sessions}
- Employees Trained: {employees_trained}
- Safety Inspections: {inspections}
- Corrective Actions: {corrective_actions}

Compliance:
OSHA Inspections: {osha_inpections}
Violations: {violations}
Fines: ${fines:,.2f}

Recommendations:
1. Enhance fall protection programs
2. Upgrade equipment safety features
3. Implement additional training modules
4. Improve incident reporting systems

Goals for Next Year:
- Reduce recordable incidents by 20%
- Achieve zero lost time injuries
- Conduct monthly safety audits
- Implement new safety management system

Report Prepared: {date}
Safety Manager: {safety_manager}
"""
]

FORM_TEMPLATES = [
    """
EMPLOYEE APPLICATION FORM

Application Date: {date}
Position Applied: {position}

PERSONAL INFORMATION:
First Name: {first_name}
Last Name: {last_name}
Middle Initial: {middle_initial}
Date of Birth: {dob}
Social Security: ***-**-{ssn_last4}

Contact Information:
Address: {address}
City: {city}
State: {state}
ZIP Code: {zip}
Phone: {phone}
Email: {email}

EDUCATION:
High School: {high_school}
Graduation: {hs_grad_year}

College: {college}
Degree: {degree}
Graduation: {college_grad_year}

EMPLOYMENT HISTORY:
Current Employer: {current_employer}
Position: {current_position}
Duration: {current_duration}
Responsibilities: {responsibilities}

Previous Employer: {prev_employer}
Position: {prev_position}
Duration: {prev_duration}

REFERENCES:
Reference 1:
Name: {ref1_name}
Relationship: {ref1_relationship}
Phone: {ref1_phone}

Reference 2:
Name: {ref2_name}
Relationship: {ref2_relationship}
Phone: {ref2_phone}

AVAILABILITY:
Start Date: {availability}
Work Hours: {work_hours}
Salary Expectation: ${salary_expectation:,}

CERTIFICATION:
I certify that all information provided is true and complete.

Signature: _________________________
Date: {date}
""",
    """
CUSTOMER FEEDBACK FORM

Survey ID: FB-{num:06d}
Date: {date}

CUSTOMER INFORMATION:
Name: {customer_name}
Email: {customer_email}
Phone: {customer_phone}
Purchase Date: {purchase_date}
Order Number: {order_number}

PRODUCT/SERVICE INFORMATION:
Product: {product_name}
Category: {product_category}
Purchase Location: {purchase_location}

SATISFACTION RATINGS (1-5):
Overall Satisfaction: {overall_satisfaction}
Product Quality: {product_quality}
Customer Service: {customer_service}
Price Value: {price_value}
Delivery Speed: {delivery_speed}

FEEDBACK QUESTIONS:
1. How did you hear about us? {hear_about_us}

2. What influenced your purchase decision? {influence_factors}

3. What did you like most about our product/service?
{positive_feedback}

4. What could be improved?
{improvement_feedback}

5. Would you recommend us to others? {recommendation}

ADDITIONAL COMMENTS:
{additional_comments}

FOLLOW-UP PERMISSION:
May we contact you for follow-up? {followup_permission}

Best way to reach you: {best_contact}

Thank you for your feedback!

Customer Service Team
{company_name}
"""
]

MANUAL_TEMPLATES = [
    """
USER MANUAL - PRODUCT {product_id}
Version {version}
Last Updated: {date}

TABLE OF CONTENTS:
1. Introduction
2. Safety Precautions
3. Installation Guide
4. Operating Instructions
5. Maintenance
6. Troubleshooting
7. Technical Specifications
8. Warranty Information

1. INTRODUCTION
Thank you for purchasing the {product_name}. This manual provides comprehensive instructions for safe and proper operation.

Package Contents:
- Main Unit: 1
- Power Adapter: 1
- User Manual: 1
- Warranty Card: 1

2. SAFETY PRECAUTIONS
WARNING: Read all safety instructions before operation.
- Keep away from water and moisture
- Use only provided power adapter
- Do not disassemble the unit
- Keep out of reach of children

3. INSTALLATION GUIDE
Step 1: Unpack all components
Step 2: Connect power adapter
Step 3: Place unit on stable surface
Step 4: Power on the device

4. OPERATING INSTRUCTIONS
Basic Operation:
- Press power button to turn on/off
- Use control panel for settings
- Follow on-screen prompts

Advanced Features:
- {feature1}
- {feature2}
- {feature3}

5. MAINTENANCE
Daily: Clean exterior with soft cloth
Weekly: Check connections
Monthly: Update software
Annually: Professional service

6. TROUBLESHOOTING
Problem: Unit won't turn on
Solution: Check power connection

Problem: Poor performance
Solution: Restart device

7. TECHNICAL SPECIFICATIONS
Power: {power_spec}
Dimensions: {dimensions}
Weight: {weight}
Operating Temperature: {temp_range}

8. WARRANTY
{warranty_info}

Contact Support:
Phone: {support_phone}
Email: {support_email}
Website: {support_website}
""",
    """
PROCEDURE MANUAL - {department}
Procedure Code: PROC-{num:05d}
Effective Date: {date}
Review Date: {review_date}

PURPOSE:
This document outlines the standard operating procedure for {procedure_name}.

SCOPE:
Applies to all {department} personnel involved in {procedure_name} activities.

RESPONSIBILITIES:
- Department Manager: {manager_name}
- Lead Technician: {lead_name}
- Staff Personnel: All team members

PROCEDURE STEPS:

1. PREPARATION
1.1 Review work order requirements
1.2 Gather necessary tools and materials
1.3 Verify safety equipment is available
1.4 Notify affected departments

2. EXECUTION
2.1 Follow safety protocols
2.2 Execute primary tasks in sequence
2.3 Document all activities
2.4 Perform quality checks

3. COMPLETION
3.1 Clean work area
3.2 Return tools to storage
3.3 Complete documentation
4.4 Report completion to supervisor

SAFETY REQUIREMENTS:
- Personal Protective Equipment (PPE): {ppe_requirements}
- Safety Training Required: {training_required}
- Emergency Procedures: {emergency_procedures}

QUALITY STANDARDS:
- Acceptance Criteria: {acceptance_criteria}
- Inspection Points: {inspection_points}
- Documentation Requirements: {doc_requirements}

REFERENCES:
- Company Policy Manual, Section {policy_section}
- Industry Standard {industry_standard}
- Regulatory Requirement {regulatory_req}

APPROVALS:
Prepared by: {prepared_by}
Approved by: {approved_by}
Date: {date}

Revision History:
Rev {revision} - {revision_date} - {revision_notes}
"""
]

LETTER_TEMPLATES = [
    """
{date}

{recipient_name}
{recipient_title}
{recipient_company}
{recipient_address}
{recipient_city}, {recipient_state} {recipient_zip}

Dear {recipient_name},

Re: {subject}

I hope this letter finds you well. I am writing to {purpose}.

{main_content}

{closing_content}

Thank you for your time and consideration. Please feel free to contact me at {phone} or {email} if you require any additional information.

Sincerely,

{sender_name}
{sender_title}
{sender_company}
{sender_address}
{sender_city}, {sender_state} {sender_zip}
{sender_phone}
{sender_email}
""",
    """
{date}

{recipient_name}
{recipient_address}
{recipient_city}, {recipient_state} {recipient_zip}

Dear {recipient_name},

{greeting}

{letter_body}

{action_required}

{closing}

Best regards,

{sender_name}
{sender_contact}

Enclosures:
{enclosures}
CC: {cc_list}
"""
]

RESUME_TEMPLATES = [
    """
RESUME

{full_name}
{address} | {phone} | {email} | {linkedin}

PROFESSIONAL SUMMARY
{professional_summary}

EXPERIENCE

{job1_title} | {job1_company} | {job1_location} | {job1_dates}
- {job1_responsibility1}
- {job1_responsibility2}
- {job1_responsibility3}
- {job1_achievement}

{job2_title} | {job2_company} | {job2_location} | {job2_dates}
- {job2_responsibility1}
- {job2_responsibility2}
- {job2_responsibility3}

EDUCATION
{degree} | {university} | {graduation_year}
- {gpa} GPA
- {honors}

SKILLS
Technical Skills: {technical_skills}
Soft Skills: {soft_skills}
Languages: {languages}

CERTIFICATIONS
{cert1_name} | {cert1_date}
{cert2_name} | {cert2_date}

PROJECTS
{project1_title} | {project1_dates}
- {project1_description}
- {project1_technologies}
- {project1_outcome}

REFERENCES
Available upon request
""",
    """
CURRICULUM VITAE

{full_name}
{phone} | {email} | {website}

PROFILE
{profile_summary}

RESEARCH INTERESTS
{research_interests}

EDUCATION
{phd_degree} | {phd_university} | {phd_year}
Dissertation: {dissertation_title}
Advisor: {advisor_name}

{masters_degree} | {masters_university} | {masters_year}
{bachelors_degree} | {bachelors_university} | {bachelors_year}

ACADEMIC EXPERIENCE
{position1} | {institution1} | {dates1}
- {teaching1}
- {research1}
- {service1}

{position2} | {institution2} | {dates2}
- {teaching2}
- {research2}

PUBLICATIONS
Peer-Reviewed Articles:
{publication1}
{publication2}
{publication3}

Conference Presentations:
{conference1}
{conference2}

GRANTS AND AWARDS
{grant1} | {amount1} | {year1}
{award1} | {year1}
{grant2} | {amount2} | {year2}

PROFESSIONAL ACTIVITIES
Reviewer: {journal_list}
Member: {professional_societies}
Conference Organizer: {conferences}

TEACHING
Courses Taught:
{course1} | {level1}
{course2} | {level2}

Student Supervision:
{thesis_students} thesis students advised
{project_students} research projects supervised

REFERENCES
{reference1} - {reference1_title}
{reference2} - {reference2_title}
{reference3} - {reference3_title}
"""
]

SPECIFICATION_TEMPLATES = [
    """
TECHNICAL SPECIFICATION
Product ID: TS-{num:06d}
Version: {version}
Date: {date}

PRODUCT OVERVIEW
Product Name: {product_name}
Model: {model_number}
Category: {category}

GENERAL SPECIFICATIONS
Dimensions: {dimensions}
Weight: {weight}
Material: {material}
Color: {color}
Warranty: {warranty_period}

PERFORMANCE SPECIFICATIONS
Power Consumption: {power_consumption}
Operating Voltage: {voltage}
Frequency Range: {frequency_range}
Operating Temperature: {temp_range}
Storage Temperature: {storage_temp}

TECHNICAL PARAMETERS
Processor: {processor}
Memory: {memory}
Storage: {storage}
Interface: {interface}
Connectivity: {connectivity}

ENVIRONMENTAL SPECIFICATIONS
Operating Humidity: {humidity}
Altitude: {altitude}
Shock Resistance: {shock_resistance}
Vibration Resistance: {vibration_resistance}

SAFETY AND COMPLIANCE
Safety Standards: {safety_standards}
Regulatory Compliance: {regulatory_compliance}
Certifications: {certifications}
RoHS Compliant: {rohs_compliant}

PACKAGING SPECIFICATIONS
Package Dimensions: {package_dimensions}
Package Weight: {package_weight}
Packaging Material: {packaging_material}
Shipping Class: {shipping_class}

QUALITY ASSURANCE
Inspection Standards: {inspection_standards}
Test Procedures: {test_procedures}
Defect Rate: {defect_rate}
Reliability: {reliability}

REVISION HISTORY
Rev {revision} - {revision_date} - {changes}

Prepared by: {prepared_by}
Approved by: {approved_by}
Department: {department}
""",
    """
REQUIREMENTS SPECIFICATION
Document ID: REQ-{num:06d}
Project: {project_name}
Version: {version}
Date: {date}

1. INTRODUCTION
1.1 Purpose: {purpose}
1.2 Scope: {scope}
1.3 Definitions: {definitions}

2. SYSTEM OVERVIEW
2.1 System Description: {system_description}
2.2 User Characteristics: {user_characteristics}
2.3 Operating Environment: {operating_environment}

3. FUNCTIONAL REQUIREMENTS
3.1 User Interface Requirements
{ui_requirements}

3.2 Business Logic Requirements
{business_requirements}

3.3 Data Management Requirements
{data_requirements}

3.4 Integration Requirements
{integration_requirements}

4. NON-FUNCTIONAL REQUIREMENTS
4.1 Performance Requirements
- Response Time: {response_time}
- Throughput: {throughput}
- Concurrent Users: {concurrent_users}
- Availability: {availability}

4.2 Security Requirements
{security_requirements}

4.3 Reliability Requirements
{reliability_requirements}

4.4 Usability Requirements
{usability_requirements}

5. CONSTRAINTS
{constraints}

6. ASSUMPTIONS AND DEPENDENCIES
{assumptions}

7. VERIFICATION CRITERIA
{verification_criteria}

8. GLOSSARY
{glossary}

DOCUMENT CONTROL
Author: {author}
Reviewers: {reviewers}
Approval: {approval}
Next Review Date: {next_review}
"""
]

# Template categories
CATEGORIES = {
    'academic_paper': ACADEMIC_TEMPLATES,
    'invoice': INVOICE_TEMPLATES,
    'contract': CONTRACT_TEMPLATES,
    'report': REPORT_TEMPLATES,
    'form': FORM_TEMPLATES,
    'manual': MANUAL_TEMPLATES,
    'letter': LETTER_TEMPLATES,
    'resume': RESUME_TEMPLATES,
    'specification': SPECIFICATION_TEMPLATES
}

# Sample data for template filling
def generate_sample_data():
    """Generate random sample data for templates."""
    return {
        'num': random.randint(1000, 9999),
        'date': (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
        'due_date': (datetime.now() + timedelta(days=random.randint(15, 60))).strftime('%Y-%m-%d'),
        'customer_name': random.choice(['Acme Corporation', 'Tech Solutions Inc', 'Global Enterprises', 'Innovate LLC']),
        'customer_address': f"{random.randint(100, 999)} Main St",
        'customer_city': random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston']),
        'customer_state': random.choice(['NY', 'CA', 'IL', 'TX']),
        'customer_zip': f"{random.randint(10000, 99999)}",
        'customer_email': f"customer{random.randint(1, 999)}@example.com",
        'qty1': random.randint(1, 10),
        'price1': round(random.uniform(100, 1000), 2),
        'qty2': random.randint(1, 5),
        'price2': round(random.uniform(50, 500), 2),
        'qty3': random.randint(1, 3),
        'price3': round(random.uniform(200, 2000), 2),
        'quarter': random.randint(1, 4),
        'year': random.randint(2022, 2024),
        'revenue': random.randint(1000000, 5000000),
        'revenue_growth': round(random.uniform(5, 25), 1),
        'net_income': random.randint(100000, 1000000),
        'margin': round(random.uniform(10, 30), 1),
        'new_customers': random.randint(100, 1000),
        'software_rev': random.randint(500000, 2000000),
        'software_growth': round(random.uniform(10, 30), 1),
        'software_share': round(random.uniform(15, 35), 1),
        'consulting_rev': random.randint(300000, 1500000),
        'consulting_growth': round(random.uniform(5, 25), 1),
        'projects_completed': random.randint(20, 100),
        'support_rev': random.randint(200000, 800000),
        'satisfaction': round(random.uniform(85, 98), 1),
        'retention': round(random.uniform(90, 99), 1),
        'employees': random.randint(50, 500),
        'product_launches': random.randint(2, 10),
        'rd_investment': random.randint(100000, 500000),
        'next_quarter': random.randint(1, 4),
        'projected_revenue': random.randint(1200000, 6000000),
        'author': random.choice(['John Smith', 'Sarah Johnson', 'Mike Davis', 'Emily Brown']),
        'first_name': random.choice(['John', 'Sarah', 'Mike', 'Emily', 'David', 'Lisa', 'James', 'Mary']),
        'last_name': random.choice(['Smith', 'Johnson', 'Davis', 'Brown', 'Wilson', 'Moore', 'Taylor', 'Anderson']),
        'middle_initial': random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']),
        'dob': f"{random.randint(1950, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        'ssn_last4': f"{random.randint(1000, 9999)}",
        'address': f"{random.randint(100, 999)} {random.choice(['Oak', 'Pine', 'Maple', 'Elm'])} St",
        'city': random.choice(['Boston', 'Seattle', 'Denver', 'Atlanta', 'Portland', 'Phoenix']),
        'state': random.choice(['MA', 'WA', 'CO', 'GA', 'OR', 'AZ']),
        'zip': f"{random.randint(10000, 99999)}",
        'phone': f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        'email': f"user{random.randint(1, 9999)}@example.com",
        'high_school': f"{random.choice(['North', 'South', 'East', 'West'])} High School",
        'hs_grad_year': random.randint(2000, 2020),
        'college': random.choice(['State University', 'Technical College', 'Business Institute']),
        'degree': random.choice(['Bachelor of Science', 'Bachelor of Arts', 'Master of Business Administration']),
        'college_grad_year': random.randint(2004, 2024),
        'current_employer': random.choice(['Tech Corp', 'Global Industries', 'Innovation Labs']),
        'current_position': random.choice(['Software Engineer', 'Project Manager', 'Business Analyst']),
        'current_duration': f"{random.randint(1, 5)} years",
        'responsibilities': random.choice(['Developing software applications', 'Managing project timelines', 'Analyzing business requirements']),
        'prev_employer': random.choice(['Previous Company A', 'Previous Company B']),
        'prev_position': random.choice(['Junior Developer', 'Team Lead', 'Consultant']),
        'prev_duration': f"{random.randint(1, 3)} years",
        'position': random.choice(['Software Developer', 'Project Manager', 'Data Analyst', 'Marketing Specialist']),
        'availability': (datetime.now() + timedelta(days=random.randint(7, 30))).strftime('%Y-%m-%d'),
        'work_hours': random.choice(['9-5', '8-4', 'Flexible', 'Remote']),
        'salary_expectation': random.randint(50000, 120000),
        'product_name': f"Product-{random.randint(100, 999)}",
        'product_id': f"PROD-{random.randint(10000, 99999)}",
        'version': f"v{random.randint(1, 5)}.{random.randint(0, 9)}",
        'power_spec': f"{random.randint(100, 500)}W",
        'dimensions': f"{random.randint(10, 50)}x{random.randint(10, 30)}x{random.randint(5, 20)} cm",
        'weight': f"{random.randint(1, 10)} kg",
        'temp_range': f"{random.randint(-10, 0)}°C to {random.randint(40, 60)}°C",
        'support_phone': "1-800-SUPPORT",
        'support_email': "support@example.com",
        'support_website': "www.example.com/support",
        'department': random.choice(['IT', 'HR', 'Finance', 'Operations', 'Marketing']),
        'procedure_name': random.choice(['Data Backup', 'System Maintenance', 'Quality Control', 'Customer Service']),
        'manager_name': random.choice(['Alice Manager', 'Bob Supervisor', 'Carol Director']),
        'lead_name': random.choice(['Dave Lead', 'Eve Specialist', 'Frank Coordinator']),
        'ppe_requirements': random.choice(['Safety glasses and gloves', 'Full protective equipment', 'Standard office attire']),
        'training_required': random.choice(['Annual safety training', 'Quarterly compliance training', 'Monthly skill updates']),
        'emergency_procedures': random.choice(['Evacuation plan A', 'Shelter in place protocol', 'Medical emergency response']),
        'acceptance_criteria': random.choice(['100% functional testing', '95% user satisfaction', 'Zero critical defects']),
        'inspection_points': random.choice(['5 quality checkpoints', '10 verification steps', '3 validation stages']),
        'doc_requirements': random.choice(['Complete documentation', 'Summary report only', 'Detailed logs']),
        'policy_section': random.choice(['Section 4.2', 'Section 7.1', 'Section 3.5']),
        'industry_standard': random.choice(['ISO 9001', 'IEEE 802.11', 'NIST SP 800-53']),
        'regulatory_req': random.choice(['FDA 21 CFR Part 11', 'GDPR Compliance', 'SOX Requirements']),
        'prepared_by': random.choice(['John Doe', 'Jane Smith', 'Bob Johnson']),
        'approved_by': random.choice(['Manager A', 'Director B', 'Supervisor C']),
        'revision': random.randint(1, 5),
        'revision_date': (datetime.now() - timedelta(days=random.randint(1, 90))).strftime('%Y-%m-%d'),
        'revision_notes': random.choice(['Updated safety procedures', 'Added new requirements', 'Clarified terminology']),
        'recipient_name': random.choice(['Mr. Anderson', 'Ms. Williams', 'Dr. Chen', 'Prof. Kumar']),
        'recipient_title': random.choice(['CEO', 'Director', 'Manager', 'President']),
        'recipient_company': random.choice(['ABC Corporation', 'XYZ Industries', 'Global Solutions']),
        'recipient_address': f"{random.randint(100, 999)} Business Ave",
        'recipient_city': random.choice(['San Francisco', 'New York', 'Chicago', 'Boston']),
        'subject': random.choice(['Business Proposal', 'Partnership Opportunity', 'Service Agreement', 'Product Inquiry']),
        'purpose': random.choice(['propose a strategic partnership', 'discuss potential collaboration', 'present our services', 'inquire about opportunities']),
        'main_content': random.choice(['Our company has been following your success and believe we could create significant value together.', 'We are impressed with your market position and see synergies between our organizations.', 'Our expertise complements your strengths and we believe this could be mutually beneficial.']),
        'closing_content': random.choice(['I look forward to your response and hope we can arrange a meeting to discuss this further.', 'Please let me know if you would like to schedule a call to explore this opportunity.', 'I am available at your convenience to discuss how we can work together.']),
        'sender_name': random.choice(['Alex Thompson', 'Jordan Lee', 'Morgan Davis', 'Casey Wilson']),
        'sender_title': random.choice(['Business Development Manager', 'Sales Director', 'Partnership Manager']),
        'sender_company': random.choice(['Innovation Partners', 'Strategic Solutions', 'Growth Ventures']),
        'sender_address': f"{random.randint(100, 999)} Partnership Blvd",
        'sender_city': random.choice(['Austin', 'Denver', 'Seattle', 'Portland']),
        'sender_state': random.choice(['TX', 'CO', 'WA', 'OR']),
        'sender_zip': f"{random.randint(10000, 99999)}",
        'sender_phone': f"555-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
        'sender_email': f"contact{random.randint(1, 999)}@example.com",
        'greeting': random.choice(['I hope this letter finds you well.', 'I am writing to you today regarding...', 'Thank you for your recent inquiry.']),
        'letter_body': random.choice(['Your recent request has been reviewed and we are pleased to inform you...', 'After careful consideration of your proposal, we have decided...', 'We would like to take this opportunity to thank you for...']),
        'action_required': random.choice(['Please sign and return the enclosed form.', 'We require your response within 10 business days.', 'No action is needed at this time.']),
        'closing': random.choice(['Sincerely', 'Best regards', 'Yours truly', 'Respectfully']),
        'sender_contact': f"{random.choice(['Phone', 'Email'])}: {random.choice(['555-123-4567', 'contact@example.com'])}",
        'enclosures': random.choice(['Brochure, Price List', 'Contract Draft', 'Product Catalog']),
        'cc_list': random.choice(['Legal Department', 'Finance Team', 'Board of Directors']),
        'full_name': random.choice(['Alexandra Johnson', 'Michael Chen', 'Sarah Williams', 'David Rodriguez']),
        'professional_summary': random.choice(['Experienced software developer with 8+ years in full-stack development.', 'Results-driven project manager specializing in agile methodologies.', 'Data scientist with expertise in machine learning and statistical analysis.']),
        'job1_title': random.choice(['Senior Software Engineer', 'Project Manager', 'Data Scientist']),
        'job1_company': random.choice(['Tech Corp', 'Data Solutions', 'Innovation Labs']),
        'job1_location': random.choice(['San Francisco, CA', 'New York, NY', 'Austin, TX']),
        'job1_dates': f"{random.randint(2018, 2020)} - Present",
        'job1_responsibility1': random.choice(['Led development of cloud-based applications', 'Managed cross-functional teams of 10+ members', 'Developed predictive models for business insights']),
        'job1_responsibility2': random.choice(['Improved system performance by 40%', 'Reduced project delivery time by 25%', 'Increased model accuracy by 15%']),
        'job1_responsibility3': random.choice(['Mentored junior developers', 'Implemented agile methodologies', 'Collaborated with stakeholders']),
        'job1_achievement': random.choice(['Received Employee of the Year award', 'Successfully delivered 5 major projects', 'Published 3 research papers']),
        'job2_title': random.choice(['Software Developer', 'Business Analyst', 'Research Assistant']),
        'job2_company': random.choice(['StartUp Inc', 'Analytics Firm', 'University Research Lab']),
        'job2_location': random.choice(['Boston, MA', 'Chicago, IL', 'Seattle, WA']),
        'job2_dates': f"{random.randint(2015, 2018)}",
        'job2_responsibility1': random.choice(['Developed web applications', 'Analyzed business requirements', 'Conducted data analysis']),
        'job2_responsibility2': random.choice(['Maintained existing systems', 'Created documentation', 'Presented findings']),
        'job2_responsibility3': random.choice(['Collaborated with teams', 'Met deadlines consistently', 'Improved processes']),
        'degree': random.choice(['Bachelor of Science in Computer Science', 'Master of Business Administration', 'PhD in Data Science']),
        'university': random.choice(['State University', 'Technical Institute', 'Business School']),
        'graduation_year': random.randint(2010, 2018),
        'gpa': round(random.uniform(3.2, 4.0), 2),
        'honors': random.choice(['Magna Cum Laude', 'Dean\'s List', 'Honor Society']),
        'technical_skills': random.choice(['Python, JavaScript, SQL, AWS', 'Java, Spring, React, Docker', 'R, Python, TensorFlow, Spark']),
        'soft_skills': random.choice(['Leadership, Communication, Problem-solving', 'Teamwork, Time Management, Adaptability', 'Critical Thinking, Creativity, Collaboration']),
        'languages': random.choice(['English (Native), Spanish (Basic)', 'English (Native), French (Fluent)', 'English (Native), Mandarin (Intermediate)']),
        'cert1_name': random.choice(['AWS Certified Solutions Architect', 'PMP Certification', 'Google Data Analytics']),
        'cert1_date': f"{random.randint(2020, 2023)}",
        'cert2_name': random.choice(['Scrum Master Certification', 'Microsoft Azure Developer', 'Tableau Desktop Specialist']),
        'cert2_date': f"{random.randint(2021, 2023)}",
        'project1_title': random.choice(['E-commerce Platform', 'Data Analytics Dashboard', 'Mobile Application']),
        'project1_dates': f"{random.randint(2022, 2023)}",
        'project1_description': random.choice(['Built a full-stack e-commerce platform', 'Created interactive data visualization dashboard', 'Developed cross-platform mobile app']),
        'project1_technologies': random.choice(['React, Node.js, MongoDB', 'Python, D3.js, PostgreSQL', 'React Native, Firebase']),
        'project1_outcome': random.choice(['Increased sales by 30%', 'Improved decision-making speed', 'Achieved 10,000+ downloads']),
        'profile_summary': random.choice(['Academic researcher with expertise in machine learning and artificial intelligence.', 'Professor specializing in data science and computational statistics.', 'Research scientist focused on theoretical computer science and algorithms.']),
        'research_interests': random.choice(['Machine Learning, Natural Language Processing, Computer Vision', 'Statistical Learning Theory, Optimization, Data Mining', 'Algorithm Design, Computational Complexity, Graph Theory']),
        'phd_degree': random.choice(['PhD in Computer Science', 'PhD in Statistics', 'PhD in Mathematics']),
        'phd_university': random.choice(['MIT', 'Stanford', 'Berkeley', 'Carnegie Mellon']),
        'phd_year': random.randint(2015, 2020),
        'dissertation_title': random.choice(['Deep Learning for Natural Language Understanding', 'Statistical Methods for Big Data Analysis', 'Efficient Algorithms for Graph Processing']),
        'advisor_name': random.choice(['Dr. Smith', 'Prof. Johnson', 'Dr. Williams']),
        'masters_degree': random.choice(['MS in Computer Science', 'MA in Statistics', 'MS in Applied Mathematics']),
        'masters_university': random.choice(['University of Washington', 'UCLA', 'University of Michigan']),
        'masters_year': random.randint(2012, 2015),
        'bachelors_degree': random.choice(['BS in Computer Science', 'BA in Mathematics', 'BS in Statistics']),
        'bachelors_university': random.choice(['State University', 'Liberal Arts College', 'Technical Institute']),
        'bachelors_year': random.randint(2008, 2012),
        'position1': random.choice(['Assistant Professor', 'Research Scientist', 'Postdoctoral Fellow']),
        'institution1': random.choice(['University Research Lab', 'Industry Research Center', 'Government Research Institute']),
        'dates1': f"{random.randint(2020, 2023)} - Present",
        'teaching1': random.choice(['Machine Learning, Data Structures, Algorithms', 'Statistics, Probability Theory', 'Computer Science, Programming']),
        'research1': random.choice(['AI research with $500K funding', 'Published 10+ peer-reviewed papers', 'Led research team of 5 members']),
        'service1': random.choice(['Program committee member for top conferences', 'Reviewer for major journals', 'Department curriculum committee']),
        'position2': random.choice(['Visiting Scholar', 'Research Assistant', 'Teaching Assistant']),
        'institution2': random.choice(['International University', 'Research Hospital', 'National Laboratory']),
        'dates2': f"{random.randint(2018, 2020)}",
        'teaching2': random.choice(['Guest lectures on specialized topics', 'Laboratory instruction', 'Tutorial sessions']),
        'research2': random.choice(['Collaborative research projects', 'Data analysis and modeling', 'Literature reviews and surveys']),
        'publication1': random.choice(['Smith, J. et al. (2023). "Novel Approaches to Machine Learning." Journal of AI Research.', 'Johnson, M. (2022). "Statistical Methods for Big Data." Statistics Journal.', 'Williams, S. (2023). "Advanced Algorithms." Computer Science Review.']),
        'publication2': random.choice(['Chen, L. et al. (2022). "Deep Learning Applications." Neural Networks Journal.', 'Davis, R. (2023). "Data Science Methodologies." Data Mining Journal.', 'Brown, K. (2022). "Computational Intelligence." AI Magazine.']),
        'publication3': random.choice(['Anderson, T. (2023). "Machine Learning Theory." ML Journal.', 'Miller, P. (2022). "Statistical Analysis." Statistics Letters.', 'Wilson, E. (2023). "Algorithm Design." Algorithms Journal.']),
        'conference1': random.choice(['International Conference on Machine Learning', 'Neural Information Processing Systems', 'International Conference on AI']),
        'conference2': random.choice(['Annual Statistics Symposium', 'Computer Science Conference', 'Data Science Summit']),
        'grant1': random.choice(['NSF Research Grant', 'DARPA Funding', 'Industry Research Grant']),
        'amount1': random.randint(100000, 1000000),
        'year1': random.randint(2020, 2023),
        'award1': random.choice(['Best Paper Award', 'Outstanding Researcher Award', 'Teaching Excellence Award']),
        'grant2': random.choice(['University Research Grant', 'Collaborative Research Funding', 'Seed Grant']),
        'amount2': random.randint(50000, 500000),
        'year2': random.randint(2021, 2023),
        'journal_list': random.choice(['Journal of Machine Learning Research, IEEE Transactions on AI', 'Statistics Journal, Data Mining Journal', 'Computer Science Journal, Algorithms Magazine']),
        'professional_societies': random.choice(['ACM, IEEE, AAAI', 'ASA, IMS, ISI', 'SIAM, AMS, INFORMS']),
        'conferences': random.choice(['Program Chair: ICML 2023', 'Organizer: AI Summit 2022', 'Workshop Chair: ML Conference 2023']),
        'course1': random.choice(['Machine Learning', 'Statistical Methods', 'Computer Algorithms']),
        'level1': random.choice(['Graduate', 'Undergraduate', 'Both']),
        'course2': random.choice(['Data Science', 'Probability Theory', 'Programming']),
        'level2': random.choice(['Undergraduate', 'Graduate', 'Both']),
        'thesis_students': random.randint(2, 8),
        'project_students': random.randint(5, 15),
        'reference1': random.choice(['Dr. John Smith - Professor, MIT', 'Prof. Mary Johnson - Department Chair, Stanford', 'Dr. Robert Williams - Research Director, Google']),
        'reference1_title': random.choice(['Professor of Computer Science', 'Department Chair', 'Research Director']),
        'reference2': random.choice(['Dr. Sarah Chen - Senior Researcher, Microsoft', 'Prof. Michael Davis - Dean, Berkeley', 'Dr. Lisa Anderson - Chief Scientist, OpenAI']),
        'reference2_title': random.choice(['Senior Researcher', 'Dean', 'Chief Scientist']),
        'reference3': random.choice(['Dr. James Wilson - Professor, Carnegie Mellon', 'Prof. Emily Brown - Department Head, UCLA', 'Dr. David Moore - Research Lead, IBM']),
        'reference3_title': random.choice(['Professor', 'Department Head', 'Research Lead']),
        'model_number': f"Model-{random.randint(1000, 9999)}",
        'category': random.choice(['Electronics', 'Software', 'Hardware', 'Industrial']),
        'material': random.choice(['Aluminum', 'Plastic', 'Steel', 'Carbon Fiber']),
        'color': random.choice(['Black', 'White', 'Silver', 'Blue']),
        'warranty_period': random.choice(['1 Year', '2 Years', '3 Years', '5 Years']),
        'power_consumption': f"{random.randint(10, 500)}W",
        'voltage': f"{random.randint(110, 240)}V",
        'frequency_range': f"{random.randint(1, 100)}Hz - {random.randint(1000, 10000)}Hz",
        'temp_range': f"-{random.randint(10, 20)}°C to {random.randint(40, 80)}°C",
        'storage_temp': f"-{random.randint(20, 40)}°C to {random.randint(60, 85)}°C",
        'processor': random.choice(['Intel i7', 'AMD Ryzen 7', 'Apple M2', 'Qualcomm Snapdragon']),
        'memory': random.choice(['8GB DDR4', '16GB DDR4', '32GB DDR5', '64GB DDR5']),
        'storage': random.choice(['256GB SSD', '512GB SSD', '1TB SSD', '2TB HDD']),
        'interface': random.choice(['USB 3.0', 'Thunderbolt 3', 'USB-C', 'HDMI 2.1']),
        'connectivity': random.choice(['WiFi 6, Bluetooth 5.0', 'WiFi 5, Bluetooth 4.2', 'Ethernet, USB']),
        'humidity': f"{random.randint(10, 90)}%",
        'altitude': f"Sea level to {random.randint(1000, 5000)}m",
        'shock_resistance': f"{random.randint(10, 100)}G",
        'vibration_resistance': f"{random.randint(5, 50)}Hz",
        'safety_standards': random.choice(['UL 94', 'IEC 60950', 'FCC Part 15']),
        'regulatory_compliance': random.choice(['FCC, CE, RoHS', 'UL, CSA, ETL', 'ISO 9001, ISO 14001']),
        'certifications': random.choice(['FCC Class B', 'CE Marked', 'UL Listed', 'Energy Star']),
        'rohs_compliant': random.choice(['Yes', 'No']),
        'package_dimensions': f"{random.randint(20, 60)}x{random.randint(20, 40)}x{random.randint(10, 30)} cm",
        'package_weight': f"{random.randint(2, 15)} kg",
        'packaging_material': random.choice(['Recycled Cardboard', 'Plastic Foam', 'Biodegradable Materials']),
        'shipping_class': random.choice(['Standard Ground', 'Express Air', 'Freight']),
        'inspection_standards': random.choice(['ISO 9001:2015', 'AS9100', 'ISO 13485']),
        'test_procedures': random.choice(['100% Functional Testing', 'Statistical Sampling', 'Accelerated Life Testing']),
        'defect_rate': f"< {round(random.uniform(0.1, 2.0), 1)}%",
        'reliability': f"{round(random.uniform(99.0, 99.9), 1)}%",
        'changes': random.choice(['Updated specifications', 'Added new features', 'Corrected errors']),
        'project_name': random.choice(['Enterprise Software System', 'Mobile Application Platform', 'Data Analytics Solution']),
        'purpose': random.choice(['Define requirements for new software system', 'Specify hardware components for industrial equipment', 'Document API specifications for web service']),
        'scope': random.choice(['This document covers all functional and non-functional requirements', 'Limited to core system components', 'Includes integration with external systems']),
        'definitions': random.choice(['System: The software application being developed', 'User: End user of the system', 'Administrator: System maintenance personnel']),
        'system_description': random.choice(['Web-based enterprise application', 'Mobile-first solution', 'Cloud-native platform']),
        'user_characteristics': random.choice(['Technical users with programming knowledge', 'Business users with basic computer skills', 'Mixed technical and non-technical users']),
        'operating_environment': random.choice(['Windows Server 2019+, SQL Server 2019+', 'AWS Cloud, PostgreSQL', 'On-premise Linux, MySQL']),
        'ui_requirements': random.choice(['Responsive web interface', 'Mobile app for iOS and Android', 'Desktop application with web interface']),
        'business_requirements': random.choice(['Real-time data processing', 'Multi-user collaboration', 'Automated workflow management']),
        'data_requirements': random.choice(['Support for 1M+ records', 'Real-time synchronization', 'Data encryption at rest']),
        'integration_requirements': random.choice(['REST API integration', 'Third-party authentication', 'Payment gateway integration']),
        'response_time': f"< {random.randint(1, 5)} seconds",
        'throughput': f"{random.randint(100, 1000)} transactions/second",
        'concurrent_users': random.randint(100, 10000),
        'availability': f"{round(random.uniform(99.5, 99.99), 2)}%",
        'security_requirements': random.choice(['OAuth 2.0 authentication', 'Role-based access control', 'Data encryption in transit']),
        'reliability_requirements': random.choice(['99.9% uptime', 'Automatic failover', 'Data backup and recovery']),
        'usability_requirements': random.choice(['508 compliance', 'Multi-language support', 'Mobile-responsive design']),
        'constraints': random.choice(['Must use existing infrastructure', 'Budget limited to $500K', 'Timeline: 6 months']),
        'assumptions': random.choice(['Users have basic computer skills', 'Network bandwidth sufficient', 'Stakeholder cooperation available']),
        'verification_criteria': random.choice(['All requirements tested and validated', 'User acceptance testing completed', 'Performance benchmarks met']),
        'glossary': random.choice(['API: Application Programming Interface', 'SaaS: Software as a Service', 'UI: User Interface']),
        'reviewers': random.choice(['Technical Lead, Product Manager', 'Architecture Team, QA Lead', 'Business Analyst, Security Officer']),
        'approval': random.choice(['Project Sponsor', 'Steering Committee', 'CTO']),
        'next_review': (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    }

def generate_sample_documents(num_docs: int = 100, storage_dir: str = "storage"):
    """Generate sample text documents for testing."""
    storage_path = Path(storage_dir)
    storage_path.mkdir(exist_ok=True)
    
    # Calculate how many documents per category
    categories_list = list(CATEGORIES.keys())
    docs_per_category = num_docs // len(categories_list)
    extra_docs = num_docs % len(categories_list)
    
    doc_count = 0
    
    for i, category in enumerate(categories_list):
        # Determine how many docs for this category
        category_docs = docs_per_category + (1 if i < extra_docs else 0)
        templates = CATEGORIES[category]
        
        for j in range(category_docs):
            # Select random template from category
            template = random.choice(templates)
            
            # Generate sample data
            sample_data = generate_sample_data()
            
            # Fill template
            try:
                content = template.format(**sample_data)
            except KeyError as e:
                print(f"Missing key {e} in template, using fallback")
                content = template
            
            # Create filename
            filename = f"{category}_{j+1:03d}.txt"
            filepath = storage_path / filename
            
            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            doc_count += 1
            print(f"Created {filename} ({category})")
    
    print(f"\nGenerated {doc_count} sample documents in {storage_dir}")
    
    # Create summary
    summary = {
        'total_documents': doc_count,
        'categories': {},
        'generation_date': datetime.now().isoformat()
    }
    
    for category in categories_list:
        category_files = list(storage_path.glob(f"{category}_*.txt"))
        summary['categories'][category] = len(category_files)
    
    summary_file = storage_path / "generation_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to {summary_file}")
    return summary

if __name__ == "__main__":
    generate_sample_documents(100, "storage")
