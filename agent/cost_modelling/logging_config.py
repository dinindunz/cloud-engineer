"""
Configuration Management for Bedrock Token Logging.

This module provides configuration classes and validation for all
logging components with environment-based configuration support.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CostCalculationModel(Enum):
    """Supported cost calculation models."""
    SONNET_4 = "sonnet-4"
    HAIKU_3 = "haiku-3"
    OPUS_3 = "opus-3"
    CUSTOM = "custom"


@dataclass
class ModelPricing:
    """Pricing configuration for a specific model."""
    input_cost_per_million: float
    output_cost_per_million: float
    model_id: str
    description: Optional[str] = None


@dataclass
class LoggingConfig:
    """
    Comprehensive configuration for Bedrock token logging.
    
    Supports environment-based configuration with validation
    and default values for all logging components.
    """
    
    # Core logging toggles
    enable_token_logging: bool = field(default_factory=lambda: os.getenv('ENABLE_TOKEN_LOGGING', 'true').lower() == 'true')
    enable_cloudwatch_metrics: bool = field(default_factory=lambda: os.getenv('ENABLE_CLOUDWATCH_METRICS', 'true').lower() == 'true')
    enable_dynamodb_logging: bool = field(default_factory=lambda: os.getenv('ENABLE_DYNAMODB_LOGGING', 'true').lower() == 'true')
    enable_structured_logging: bool = field(default_factory=lambda: os.getenv('ENABLE_STRUCTURED_LOGGING', 'true').lower() == 'true')
    
    # AWS Configuration
    aws_region: str = field(default_factory=lambda: os.getenv('AWS_REGION', 'ap-southeast-2'))
    
    # CloudWatch Configuration
    cloudwatch_namespace: str = field(default_factory=lambda: os.getenv('CLOUDWATCH_NAMESPACE', 'BedrockUsage'))
    cloudwatch_log_group: str = field(default_factory=lambda: os.getenv('CLOUDWATCH_LOG_GROUP', '/aws/bedrock/token-usage'))
    
    # DynamoDB Configuration
    dynamodb_table_name: str = field(default_factory=lambda: os.getenv('DYNAMODB_TABLE_NAME', 'bedrock-token-usage'))
    retention_days: int = field(default_factory=lambda: int(os.getenv('RETENTION_DAYS', '90')))
    
    # Cost Calculation Configuration
    cost_model: CostCalculationModel = field(default_factory=lambda: CostCalculationModel(os.getenv('COST_MODEL', 'sonnet-4')))
    custom_pricing: Optional[Dict[str, ModelPricing]] = None
    
    # Logging Configuration
    log_level: LogLevel = field(default_factory=lambda: LogLevel(os.getenv('LOG_LEVEL', 'INFO')))
    log_retention_days: int = field(default_factory=lambda: int(os.getenv('LOG_RETENTION_DAYS', '30')))
    
    # Performance Configuration
    async_logging: bool = field(default_factory=lambda: os.getenv('ASYNC_LOGGING', 'true').lower() == 'true')
    batch_size: int = field(default_factory=lambda: int(os.getenv('BATCH_SIZE', '25')))
    flush_interval_seconds: int = field(default_factory=lambda: int(os.getenv('FLUSH_INTERVAL_SECONDS', '60')))
    
    # Circuit Breaker Configuration
    enable_circuit_breaker: bool = field(default_factory=lambda: os.getenv('ENABLE_CIRCUIT_BREAKER', 'true').lower() == 'true')
    circuit_breaker_failure_threshold: int = field(default_factory=lambda: int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', '5')))
    circuit_breaker_recovery_timeout: int = field(default_factory=lambda: int(os.getenv('CIRCUIT_BREAKER_RECOVERY_TIMEOUT', '60')))
    
    # Cost Alerting Configuration
    enable_cost_alerts: bool = field(default_factory=lambda: os.getenv('ENABLE_COST_ALERTS', 'false').lower() == 'true')
    daily_cost_threshold: float = field(default_factory=lambda: float(os.getenv('DAILY_COST_THRESHOLD', '100.0')))
    hourly_cost_threshold: float = field(default_factory=lambda: float(os.getenv('HOURLY_COST_THRESHOLD', '10.0')))
    alert_sns_topic_arn: Optional[str] = field(default_factory=lambda: os.getenv('ALERT_SNS_TOPIC_ARN'))
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
        self._setup_default_pricing()
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        errors = []
        
        # Validate retention days
        if self.retention_days <= 0:
            errors.append("retention_days must be positive")
        
        if self.log_retention_days <= 0:
            errors.append("log_retention_days must be positive")
        
        # Validate batch size
        if self.batch_size <= 0 or self.batch_size > 25:
            errors.append("batch_size must be between 1 and 25")
        
        # Validate flush interval
        if self.flush_interval_seconds <= 0:
            errors.append("flush_interval_seconds must be positive")
        
        # Validate circuit breaker settings
        if self.circuit_breaker_failure_threshold <= 0:
            errors.append("circuit_breaker_failure_threshold must be positive")
        
        if self.circuit_breaker_recovery_timeout <= 0:
            errors.append("circuit_breaker_recovery_timeout must be positive")
        
        # Validate cost thresholds
        if self.daily_cost_threshold < 0:
            errors.append("daily_cost_threshold must be non-negative")
        
        if self.hourly_cost_threshold < 0:
            errors.append("hourly_cost_threshold must be non-negative")
        
        # Validate AWS region
        if not self.aws_region:
            errors.append("aws_region cannot be empty")
        
        # Validate table and namespace names
        if not self.dynamodb_table_name:
            errors.append("dynamodb_table_name cannot be empty")
        
        if not self.cloudwatch_namespace:
            errors.append("cloudwatch_namespace cannot be empty")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
    
    def _setup_default_pricing(self) -> None:
        """Setup default pricing models."""
        default_pricing = {
            CostCalculationModel.SONNET_4: ModelPricing(
                input_cost_per_million=3.0,
                output_cost_per_million=15.0,
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                description="Claude 3.5 Sonnet v2"
            ),
            CostCalculationModel.HAIKU_3: ModelPricing(
                input_cost_per_million=0.25,
                output_cost_per_million=1.25,
                model_id="anthropic.claude-3-haiku-20240307-v1:0",
                description="Claude 3 Haiku"
            ),
            CostCalculationModel.OPUS_3: ModelPricing(
                input_cost_per_million=15.0,
                output_cost_per_million=75.0,
                model_id="anthropic.claude-3-opus-20240229-v1:0",
                description="Claude 3 Opus"
            )
        }
        
        if self.custom_pricing is None:
            self.custom_pricing = {}
        
        # Add default pricing for models not in custom pricing
        for model, pricing in default_pricing.items():
            if model not in self.custom_pricing:
                self.custom_pricing[model.value] = pricing
    
    def get_model_pricing(self, model_id: str) -> Optional[ModelPricing]:
        """
        Get pricing information for a specific model.
        
        Args:
            model_id: Bedrock model identifier
            
        Returns:
            ModelPricing object or None if not found
        """
        # First check custom pricing by model_id
        for pricing in self.custom_pricing.values():
            if isinstance(pricing, ModelPricing) and pricing.model_id == model_id:
                return pricing
        
        # Check by cost model key
        if self.cost_model.value in self.custom_pricing:
            return self.custom_pricing[self.cost_model.value]
        
        # Fallback to Sonnet 4 pricing
        return self.custom_pricing.get('sonnet-4')
    
    def add_custom_model_pricing(self,
                                key: str,
                                model_id: str,
                                input_cost_per_million: float,
                                output_cost_per_million: float,
                                description: Optional[str] = None) -> None:
        """
        Add custom pricing for a model.
        
        Args:
            key: Unique key for the pricing model
            model_id: Bedrock model identifier
            input_cost_per_million: Cost per million input tokens
            output_cost_per_million: Cost per million output tokens
            description: Optional description
        """
        if self.custom_pricing is None:
            self.custom_pricing = {}
        
        self.custom_pricing[key] = ModelPricing(
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            model_id=model_id,
            description=description
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        config_dict = {}
        
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, Enum):
                config_dict[field_name] = field_value.value
            elif isinstance(field_value, dict) and field_name == 'custom_pricing':
                # Handle custom pricing serialization
                pricing_dict = {}
                for key, pricing in field_value.items():
                    if isinstance(pricing, ModelPricing):
                        pricing_dict[key] = {
                            'input_cost_per_million': pricing.input_cost_per_million,
                            'output_cost_per_million': pricing.output_cost_per_million,
                            'model_id': pricing.model_id,
                            'description': pricing.description
                        }
                    else:
                        pricing_dict[key] = pricing
                config_dict[field_name] = pricing_dict
            else:
                config_dict[field_name] = field_value
        
        return config_dict
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'LoggingConfig':
        """
        Create configuration from dictionary.
        
        Args:
            config_dict: Dictionary with configuration values
            
        Returns:
            LoggingConfig instance
        """
        # Handle enum conversions
        if 'cost_model' in config_dict and isinstance(config_dict['cost_model'], str):
            config_dict['cost_model'] = CostCalculationModel(config_dict['cost_model'])
        
        if 'log_level' in config_dict and isinstance(config_dict['log_level'], str):
            config_dict['log_level'] = LogLevel(config_dict['log_level'])
        
        # Handle custom pricing conversion
        if 'custom_pricing' in config_dict and isinstance(config_dict['custom_pricing'], dict):
            custom_pricing = {}
            for key, pricing_data in config_dict['custom_pricing'].items():
                if isinstance(pricing_data, dict):
                    custom_pricing[key] = ModelPricing(**pricing_data)
                else:
                    custom_pricing[key] = pricing_data
            config_dict['custom_pricing'] = custom_pricing
        
        return cls(**config_dict)
    
    def get_environment_variables(self) -> Dict[str, str]:
        """
        Get environment variables for this configuration.
        
        Returns:
            Dictionary of environment variable names and values
        """
        env_vars = {
            'ENABLE_TOKEN_LOGGING': str(self.enable_token_logging).lower(),
            'ENABLE_CLOUDWATCH_METRICS': str(self.enable_cloudwatch_metrics).lower(),
            'ENABLE_DYNAMODB_LOGGING': str(self.enable_dynamodb_logging).lower(),
            'ENABLE_STRUCTURED_LOGGING': str(self.enable_structured_logging).lower(),
            'AWS_REGION': self.aws_region,
            'CLOUDWATCH_NAMESPACE': self.cloudwatch_namespace,
            'CLOUDWATCH_LOG_GROUP': self.cloudwatch_log_group,
            'DYNAMODB_TABLE_NAME': self.dynamodb_table_name,
            'RETENTION_DAYS': str(self.retention_days),
            'COST_MODEL': self.cost_model.value,
            'LOG_LEVEL': self.log_level.value,
            'LOG_RETENTION_DAYS': str(self.log_retention_days),
            'ASYNC_LOGGING': str(self.async_logging).lower(),
            'BATCH_SIZE': str(self.batch_size),
            'FLUSH_INTERVAL_SECONDS': str(self.flush_interval_seconds),
            'ENABLE_CIRCUIT_BREAKER': str(self.enable_circuit_breaker).lower(),
            'CIRCUIT_BREAKER_FAILURE_THRESHOLD': str(self.circuit_breaker_failure_threshold),
            'CIRCUIT_BREAKER_RECOVERY_TIMEOUT': str(self.circuit_breaker_recovery_timeout),
            'ENABLE_COST_ALERTS': str(self.enable_cost_alerts).lower(),
            'DAILY_COST_THRESHOLD': str(self.daily_cost_threshold),
            'HOURLY_COST_THRESHOLD': str(self.hourly_cost_threshold)
        }
        
        if self.alert_sns_topic_arn:
            env_vars['ALERT_SNS_TOPIC_ARN'] = self.alert_sns_topic_arn
        
        return env_vars
    
    def setup_logging(self) -> None:
        """
        Setup Python logging based on configuration.
        """
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.log_level.value),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if not self.enable_structured_logging
            else '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set specific logger levels
        bedrock_logger = logging.getLogger('bedrock_token_logging')
        bedrock_logger.setLevel(getattr(logging, self.log_level.value))
        
        # Suppress boto3 debug logs unless explicitly requested
        if self.log_level != LogLevel.DEBUG:
            logging.getLogger('boto3').setLevel(logging.WARNING)
            logging.getLogger('botocore').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)


def load_config_from_file(file_path: str) -> LoggingConfig:
    """
    Load configuration from JSON or YAML file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        LoggingConfig instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    import json
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            if file_path.endswith('.json'):
                config_data = json.load(f)
            elif file_path.endswith(('.yml', '.yaml')):
                try:
                    import yaml
                    config_data = yaml.safe_load(f)
                except ImportError:
                    raise ValueError("PyYAML is required to load YAML configuration files")
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        
        return LoggingConfig.from_dict(config_data)
        
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {file_path}: {e}")


def save_config_to_file(config: LoggingConfig, file_path: str) -> None:
    """
    Save configuration to JSON or YAML file.
    
    Args:
        config: LoggingConfig instance
        file_path: Path to save configuration file
        
    Raises:
        ValueError: If file format is unsupported
    """
    import json
    
    config_dict = config.to_dict()
    
    try:
        with open(file_path, 'w') as f:
            if file_path.endswith('.json'):
                json.dump(config_dict, f, indent=2, default=str)
            elif file_path.endswith(('.yml', '.yaml')):
                try:
                    import yaml
                    yaml.dump(config_dict, f, default_flow_style=False)
                except ImportError:
                    raise ValueError("PyYAML is required to save YAML configuration files")
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        
        logger.info(f"Configuration saved to {file_path}")
        
    except Exception as e:
        raise ValueError(f"Failed to save configuration to {file_path}: {e}")


def get_default_config() -> LoggingConfig:
    """
    Get default configuration with environment variable overrides.
    
    Returns:
        LoggingConfig instance with defaults
    """
    return LoggingConfig()


def validate_aws_permissions(config: LoggingConfig) -> Dict[str, bool]:
    """
    Validate AWS permissions for the configured services.
    
    Args:
        config: LoggingConfig instance
        
    Returns:
        Dictionary with permission validation results
    """
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    
    results = {
        'bedrock_runtime': False,
        'cloudwatch': False,
        'dynamodb': False,
        'logs': False
    }
    
    try:
        # Test Bedrock Runtime permissions
        bedrock_client = boto3.client('bedrock-runtime', region_name=config.aws_region)
        # We can't test invoke_model without actually calling it, so just check client creation
        results['bedrock_runtime'] = True
        
        # Test CloudWatch permissions
        if config.enable_cloudwatch_metrics:
            cloudwatch_client = boto3.client('cloudwatch', region_name=config.aws_region)
            cloudwatch_client.list_metrics(Namespace=config.cloudwatch_namespace, MaxRecords=1)
            results['cloudwatch'] = True
        
        # Test DynamoDB permissions
        if config.enable_dynamodb_logging:
            dynamodb_client = boto3.client('dynamodb', region_name=config.aws_region)
            try:
                dynamodb_client.describe_table(TableName=config.dynamodb_table_name)
                results['dynamodb'] = True
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Table doesn't exist, but we have permissions
                    results['dynamodb'] = True
                else:
                    results['dynamodb'] = False
        
        # Test CloudWatch Logs permissions
        if config.enable_structured_logging:
            logs_client = boto3.client('logs', region_name=config.aws_region)
            try:
                logs_client.describe_log_groups(logGroupNamePrefix=config.cloudwatch_log_group, limit=1)
                results['logs'] = True
            except ClientError:
                results['logs'] = False
        
    except NoCredentialsError:
        logger.error("AWS credentials not found")
    except Exception as e:
        logger.error(f"Error validating AWS permissions: {e}")
    
    return results
