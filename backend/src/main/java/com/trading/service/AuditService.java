package com.trading.service;

import com.trading.entity.AuditLog;
import com.trading.repository.AuditLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Service for audit logging with hash chaining
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditService {

    private final AuditLogRepository auditLogRepository;

    /**
     * Get recent audit entries
     */
    public List<AuditLog> getRecentAuditLogs(int limit) {
        return auditLogRepository.findByOrderByTimestampDesc(PageRequest.of(0, limit));
    }

    /**
     * Get audit logs by event type
     */
    public List<AuditLog> getByEventType(String eventType) {
        return auditLogRepository.findByEventTypeOrderByTimestampDesc(eventType);
    }

    /**
     * Get audit logs for entity
     */
    public List<AuditLog> getByEntity(String entityType, String entityId) {
        return auditLogRepository.findByEntity(entityType, entityId);
    }

    /**
     * Get audit logs since timestamp
     */
    public List<AuditLog> getAuditLogsSince(Instant since) {
        return auditLogRepository.findSince(since);
    }

    /**
     * Create a new audit log entry with hash chaining
     */
    @Transactional
    public AuditLog createAuditLog(String eventType, String actor, String action,
                                    String entityType, String entityId,
                                    Map<String, Object> beforeState, Map<String, Object> afterState,
                                    String reasoning, Map<String, Object> extraData) {
        
        // Get previous hash for chaining
        String prevHash = auditLogRepository.findLast()
                .map(AuditLog::getHash)
                .orElse(null);
        
        // Calculate hash
        String hash = calculateHash(eventType, actor, action, entityType, entityId, 
                                     beforeState, afterState, prevHash);
        
        AuditLog entry = AuditLog.builder()
                .eventType(eventType)
                .actor(actor)
                .action(action)
                .entityType(entityType)
                .entityId(entityId)
                .beforeState(beforeState)
                .afterState(afterState)
                .reasoning(reasoning)
                .extraData(extraData != null ? extraData : Map.of())
                .prevHash(prevHash)
                .hash(hash)
                .build();
        
        return auditLogRepository.save(entry);
    }

    /**
     * Log a trade event
     */
    public AuditLog logTradeEvent(String action, String positionId, 
                                   Map<String, Object> beforeState, Map<String, Object> afterState,
                                   String reasoning) {
        return createAuditLog("TRADE", "system", action, "position", positionId,
                              beforeState, afterState, reasoning, null);
    }

    /**
     * Log a system event
     */
    public AuditLog logSystemEvent(String action, String reasoning) {
        return createAuditLog("SYSTEM", "system", action, null, null,
                              null, null, reasoning, null);
    }

    private String calculateHash(String eventType, String actor, String action,
                                  String entityType, String entityId,
                                  Map<String, Object> beforeState, Map<String, Object> afterState,
                                  String prevHash) {
        try {
            StringBuilder sb = new StringBuilder();
            sb.append(eventType).append("|");
            sb.append(actor).append("|");
            sb.append(action).append("|");
            sb.append(entityType != null ? entityType : "").append("|");
            sb.append(entityId != null ? entityId : "").append("|");
            sb.append(beforeState != null ? beforeState.toString() : "").append("|");
            sb.append(afterState != null ? afterState.toString() : "").append("|");
            sb.append(prevHash != null ? prevHash : "");
            
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(sb.toString().getBytes(StandardCharsets.UTF_8));
            
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
            
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }
}

