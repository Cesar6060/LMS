"""
Utility functions for assignment late penalty calculation.
"""
from decimal import Decimal


def calculate_late_penalty(submission, assignment):
    """
    Calculate late penalty points based on assignment settings.

    Args:
        submission: The Submission instance
        assignment: The Assignment instance

    Returns:
        Decimal: The penalty points to be deducted
    """
    # No penalty if late penalty is not configured
    if not assignment.late_penalty_percent:
        return Decimal('0')

    # No penalty if no due date or submission time
    if not assignment.due_date or not submission.submitted_at:
        return Decimal('0')

    # No penalty if submitted on time
    if submission.submitted_at <= assignment.due_date:
        return Decimal('0')

    # Calculate time late
    time_late = submission.submitted_at - assignment.due_date

    # Calculate units late based on interval
    if assignment.late_penalty_interval == 'hour':
        units_late = Decimal(str(time_late.total_seconds())) / Decimal('3600')
    else:  # day
        # Ceiling: any partial day counts as a full day
        total_seconds = time_late.total_seconds()
        days = total_seconds / 86400  # seconds in a day
        units_late = Decimal(str(int(days) + (1 if total_seconds % 86400 > 0 else 0)))

    # Calculate penalty as percentage
    penalty_percent = units_late * Decimal(str(assignment.late_penalty_percent))

    # Cap at max penalty if configured
    if assignment.max_late_penalty:
        penalty_percent = min(penalty_percent, Decimal(str(assignment.max_late_penalty)))

    # Convert percentage to points (based on assignment max_points)
    penalty_points = (penalty_percent / Decimal('100')) * Decimal(str(assignment.max_points))

    return round(penalty_points, 2)
