# Copyright 2017, Inderpreet Singh, All rights reserved.
# LftpJobStatus is now a type alias for the backend-agnostic JobStatus.
# This preserves backward compatibility for the lftp module and its tests.

from common.job_status import JobStatus

# Re-export as LftpJobStatus for backward compatibility
LftpJobStatus = JobStatus
