from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger
from remind.domain.models import model_manager
from remind.models.llms import LanguageModel


def token_count(input_string) -> int:
    """
    Count the number of tokens in the input string using the 'o200k_base' encoding.

    Args:
        input_string (str): The input string to count tokens for.

    Returns:
        int: The number of tokens in the input string.
    """
    import tiktoken

    encoding = tiktoken.get_encoding("o200k_base")
    tokens = encoding.encode(input_string)
    token_count = len(tokens)
    return token_count

def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    """
    Returns the best model to use based on the context size and on whether there is a specific model being requested in Config.
    If context > 105_000, returns the large_context_model
    If model_id is specified in Config, returns that model
    Otherwise, returns the default model for the given type
    """
    tokens = token_count(content)

    if tokens > 105_000:
        logger.debug(
            f"Using large context model because the content has {tokens} tokens"
        )
        model = model_manager.get_default_model("large_context", **kwargs)
    elif model_id:
        model = model_manager.get_model(model_id, **kwargs)
    else:
        model = model_manager.get_default_model(default_type, **kwargs)

    assert isinstance(model, LanguageModel), f"Model is not a LanguageModel: {model}"
    return model.to_langchain()
