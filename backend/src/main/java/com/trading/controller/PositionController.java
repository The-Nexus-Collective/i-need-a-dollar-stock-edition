package com.trading.controller;

import com.trading.dto.PositionDTO;
import com.trading.service.PositionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Position API endpoints
 */
@RestController
@RequestMapping("/api/positions")
@RequiredArgsConstructor
public class PositionController {

    private final PositionService positionService;

    @GetMapping
    public List<PositionDTO> getPositions(
            @RequestParam(defaultValue = "open") String status,
            @RequestParam(defaultValue = "100") int limit) {
        
        if ("open".equalsIgnoreCase(status)) {
            return positionService.getOpenPositions();
        } else {
            return positionService.getClosedPositions(limit);
        }
    }

    @GetMapping("/open")
    public List<PositionDTO> getOpenPositions() {
        return positionService.getOpenPositions();
    }

    @GetMapping("/closed")
    public List<PositionDTO> getClosedPositions(@RequestParam(defaultValue = "100") int limit) {
        return positionService.getClosedPositions(limit);
    }

    @GetMapping("/{id}")
    public ResponseEntity<PositionDTO> getPosition(@PathVariable String id) {
        return positionService.getPositionById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/symbol/{symbol}")
    public ResponseEntity<PositionDTO> getPositionBySymbol(@PathVariable String symbol) {
        return positionService.getOpenPositionBySymbol(symbol)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/count")
    public Map<String, Integer> getPositionCount() {
        return Map.of("count", positionService.countOpenPositions());
    }
}

