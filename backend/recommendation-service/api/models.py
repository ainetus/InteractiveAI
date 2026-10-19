from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class UseCaseModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    manager_class = db.Column(db.String(255), nullable=False)


class RecommendationJob(db.Model):
    """A request for recommendations, answered agent by agent (see api/jobs.py)."""

    id = db.Column(db.String(36), primary_key=True)
    use_case = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)


class RecommendationJobAgent(db.Model):
    """One agent of a job: its answer, once it has one.

    No foreign key to the job: delete_all_data empties the tables in any order.
    """

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(36), nullable=False, index=True)
    # Order the agents' recommendations are listed in
    position = db.Column(db.Integer, nullable=False)
    agent_id = db.Column(db.String(50), nullable=False)
    agent_name = db.Column(db.String(255))
    # pending, done or failed
    status = db.Column(db.String(10), nullable=False)
    recommendations = db.Column(db.JSON)
    # Still pending after this, the agent is reported failed: its answer can
    # no longer come (the service restarted while it was being asked)
    deadline = db.Column(db.DateTime, nullable=False)
