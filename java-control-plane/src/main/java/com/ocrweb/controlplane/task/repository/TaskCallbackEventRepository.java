package com.ocrweb.controlplane.task.repository;

import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TaskCallbackEventRepository extends JpaRepository<TaskCallbackEventEntity, Long> {
    boolean existsByEventId(String eventId);

    java.util.List<TaskCallbackEventEntity> findByTaskIdOrderByCreatedAtAscIdAsc(Long taskId);
}
