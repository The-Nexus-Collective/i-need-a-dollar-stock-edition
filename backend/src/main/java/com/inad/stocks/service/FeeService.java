package com.inad.stocks.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Service for calculating trading fees based on Binance VIP tier structure.
 * 
 * Fees are calculated on NOTIONAL value (not margin).
 * Supports maker/taker differentiation and VIP tier discounts.
 */
@Slf4j
@Service
public class FeeService {
    
    /**
     * Binance Futures VIP Tiers based on 30-day trading volume.
     */
    public enum VipTier {
        VIP_0(0L,            "0.0002", "0.0004"),   // Maker 0.02%, Taker 0.04%
        VIP_1(250_000L,      "0.00016", "0.0004"),  // Maker 0.016%, Taker 0.04%
        VIP_2(2_500_000L,    "0.00014", "0.00035"), // Maker 0.014%, Taker 0.035%
        VIP_3(7_500_000L,    "0.00012", "0.00032"), // Maker 0.012%, Taker 0.032%
        VIP_4(22_500_000L,   "0.00010", "0.00030"), // Maker 0.01%, Taker 0.03%
        VIP_5(50_000_000L,   "0.00008", "0.00027"), // Maker 0.008%, Taker 0.027%
        VIP_6(100_000_000L,  "0.00006", "0.00025"), // Maker 0.006%, Taker 0.025%
        VIP_7(200_000_000L,  "0.00004", "0.00022"), // Maker 0.004%, Taker 0.022%
        VIP_8(400_000_000L,  "0.00002", "0.00020"), // Maker 0.002%, Taker 0.02%
        VIP_9(750_000_000L,  "0.00000", "0.00017"); // Maker 0%, Taker 0.017%
        
        public final long volumeThreshold;
        public final BigDecimal makerFee;
        public final BigDecimal takerFee;
        
        VipTier(long threshold, String maker, String taker) {
            this.volumeThreshold = threshold;
            this.makerFee = new BigDecimal(maker);
            this.takerFee = new BigDecimal(taker);
        }
    }
    
    @Value("${trading.vip-tier:VIP_0}")
    private String vipTierConfig;
    
    private VipTier currentTier;
    
    /**
     * Get the current VIP tier.
     */
    public VipTier getCurrentTier() {
        if (currentTier == null) {
            try {
                currentTier = VipTier.valueOf(vipTierConfig);
            } catch (IllegalArgumentException e) {
                log.warn("Invalid VIP tier config '{}', defaulting to VIP_0", vipTierConfig);
                currentTier = VipTier.VIP_0;
            }
        }
        return currentTier;
    }
    
    /**
     * Get the taker fee rate for the current VIP tier.
     */
    public BigDecimal getTakerFeeRate() {
        return getCurrentTier().takerFee;
    }
    
    /**
     * Get the maker fee rate for the current VIP tier.
     */
    public BigDecimal getMakerFeeRate() {
        return getCurrentTier().makerFee;
    }
    
    /**
     * Calculate trading fee for a given notional value.
     * 
     * @param notional The notional value (position size in USDT)
     * @param isMaker true for limit orders, false for market orders
     * @return The fee amount in USDT
     */
    public BigDecimal calculateFee(BigDecimal notional, boolean isMaker) {
        if (notional == null || notional.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal rate = isMaker ? getMakerFeeRate() : getTakerFeeRate();
        return notional.multiply(rate).setScale(8, RoundingMode.HALF_UP);
    }
    
    /**
     * Calculate taker fee (for market orders, which Grok uses).
     */
    public BigDecimal calculateTakerFee(BigDecimal notional) {
        return calculateFee(notional, false);
    }
    
    /**
     * Calculate maker fee (for limit orders).
     */
    public BigDecimal calculateMakerFee(BigDecimal notional) {
        return calculateFee(notional, true);
    }
    
    /**
     * Get fee breakdown for a trade.
     */
    public FeeBreakdown getFeeBreakdown(BigDecimal notional, boolean isMaker) {
        BigDecimal fee = calculateFee(notional, isMaker);
        BigDecimal rate = isMaker ? getMakerFeeRate() : getTakerFeeRate();
        
        return new FeeBreakdown(
            fee,
            rate,
            isMaker ? "MAKER" : "TAKER",
            getCurrentTier().name()
        );
    }
    
    /**
     * Fee breakdown record for detailed fee information.
     */
    public record FeeBreakdown(
        BigDecimal feeAmount,
        BigDecimal feeRate,
        String feeType,
        String vipTier
    ) {}
    
    /**
     * Set VIP tier programmatically (for testing or dynamic updates).
     */
    public void setVipTier(VipTier tier) {
        this.currentTier = tier;
        log.info("VIP tier set to {}: Maker={}, Taker={}", 
            tier.name(), tier.makerFee, tier.takerFee);
    }
}

