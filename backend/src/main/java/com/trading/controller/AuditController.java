package com.trading.controller;

import com.trading.entity.AuditLog;
import com.trading.service.AuditService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * Audit log API endpoints
 */
@RestController
@RequestMapping("/api/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditService auditService;

    @GetMapping
    public List<AuditLog> getAuditLogs(@RequestParam(defaultValue = "100") int limit) {
        return auditService.getRecentAuditLogs(limit);
    }

    @GetMapping("/type/{eventType}")
    public List<AuditLog> getByEventType(@PathVariable String eventType) {
        return auditService.getByEventType(eventType);
    }

    @GetMapping("/entity/{entityType}/{entityId}")
    public List<AuditLog> getByEntity(
            @PathVariable String entityType,
            @PathVariable String entityId) {
        return auditService.getByEntity(entityType, entityId);
    }

    @GetMapping("/today")
    public List<AuditLog> getTodaysLogs() {
        return auditService.getAuditLogsSince(Instant.now().truncatedTo(ChronoUnit.DAYS));
    }
}

