"""Cross-provider deduplication without hiding distinct Benin vacancies."""
from app.services.benin_aggregation import combine_benin_local_jobs
from app.services.jsearch import JSearchJob


def job(source, identifier, title, company, location):
    return JSearchJob(
        provider_job_id=identifier, title=title, company=company,
        location=location, description="", apply_url="https://example.test/jobs/" + identifier,
        posted_at=None, salary_min=None, salary_max=None, salary_currency=None,
        employment_type=None, remote_status=None, source=source,
    )


def test_same_employer_title_city_collapses_cross_source_duplicate():
    first = job("devglobaljobs", "a", "Développeur Python", "Société Bénin", "Cotonou, Bénin")
    duplicate = job("careerjet", "b", "Developpeur Python", "Societe Benin", "Cotonou")
    unique = job("careerjet", "c", "Data Analyst", "Other Co", "Porto-Novo")
    assert combine_benin_local_jobs([first], [duplicate, unique], 20) == [first, unique]


def test_same_role_different_company_or_city_is_not_hidden():
    first = job("devglobaljobs", "a", "Data Analyst", "Employer A", "Cotonou")
    different_company = job("careerjet", "b", "Data Analyst", "Employer B", "Cotonou")
    different_city = job("careerjet", "c", "Data Analyst", "Employer A", "Porto-Novo")
    assert combine_benin_local_jobs([first], [different_company, different_city], 20) == [
        first, different_company, different_city
    ]


def test_unknown_workplace_is_not_fuzzily_deduplicated():
    first = job("devglobaljobs", "a", "Data Analyst", "Employer A", "")
    second = job("careerjet", "b", "Data Analyst", "Employer A", "")
    assert len(combine_benin_local_jobs([first], [second], 20)) == 2


def test_same_source_id_is_suppressed_even_if_metadata_changed():
    first = job("careerjet", "ident", "Old title", "Employer A", "Cotonou")
    edited = job("careerjet", "ident", "Updated title", "Employer A", "Cotonou")
    assert combine_benin_local_jobs([first], [edited], 20) == [first]


def test_limit_applied_after_unique_merge():
    first = job("devglobaljobs", "a", "Analyst", "Company", "Cotonou")
    duplicate = job("careerjet", "b", "Analyst", "Company", "Cotonou")
    unique = job("careerjet", "c", "Developer", "Other Company", "Cotonou")
    assert combine_benin_local_jobs([first], [duplicate, unique], 2) == [first, unique]


def test_without_publisher_jobs_keyless_results_are_unchanged():
    first = job("devglobaljobs", "a", "Analyst", "A", "Cotonou")
    assert combine_benin_local_jobs([first], [], 20) == [first]

def test_full_primary_page_does_not_crowd_out_secondary_provider():
    free = [
        job("devglobaljobs", f"free-{i}", f"Free job {i}", "Employer A", "Cotonou")
        for i in range(20)
    ]
    publisher = [
        job("careerjet", f"paid-{i}", f"Publisher job {i}", "Employer B", "Cotonou")
        for i in range(20)
    ]
    combined = combine_benin_local_jobs(free, publisher, 20)
    assert len(combined) == 20
    assert {item.source for item in combined} == {"devglobaljobs", "careerjet"}
    assert sum(item.source == "careerjet" for item in combined) == 10


def test_three_sources_interleaved_with_bounded_results():
    local = [job("devglobaljobs", f"l-{i}", f"Local role {i}", "Local Co", "Cotonou") for i in range(20)]
    publisher = [job("careerjet", f"c-{i}", f"Office role {i}", "Publisher Co", "Porto-Novo") for i in range(20)]
    remote = [job("remotive", f"r-{i}", f"Remote role {i}", "Remote Co", "Remote — Worldwide") for i in range(20)]
    for item in remote:
        item.remote_status = "REMOTE"
    combined = combine_benin_local_jobs(local, publisher, 20, tertiary=remote)
    assert len(combined) == 20
    assert {item.source for item in combined} == {"devglobaljobs", "careerjet", "remotive"}
    assert len([item for item in combined if item.source == "remotive"]) >= 6
    assert all(item.remote_status == "REMOTE" for item in combined if item.source == "remotive")


def test_eligible_remote_job_not_suppressed_by_local_same_employer_title():
    local = job("devglobaljobs", "local", "Analyst", "Employer A", "Cotonou")
    remote = job("remotive", "remote", "Analyst", "Employer A", "Remote — Africa")
    remote.remote_status = "REMOTE"
    assert combine_benin_local_jobs([local], [], 20, tertiary=[remote]) == [local, remote]
