#!/usr/bin/env python3
import os


def create_directory_structure():
    """Create the Hyperliquid strategy directory structure."""
    base_dir = "hyperliquid_strategy"

    # Define the directory structure with files
    structure = {
        '': ['__init__.py', 'config.py', 'main.py'],
        'core': ['__init__.py', 'exchange.py', 'position_manager.py', 'order_executor.py', 'logger.py'],
        'data': ['__init__.py', 'market_data.py', 'user_data.py', 'persistence.py'],
        'strategies': ['__init__.py', 'base_strategy.py'],
        'strategies/market_making': ['__init__.py', 'basic_mm.py'],
        'strategies/arb': ['__init__.py', 'cross_exchange.py'],
        'strategies/trend_following': ['__init__.py', 'momentum.py'],
        'utils': ['__init__.py', 'constants.py', 'helpers.py', 'validators.py'],
        'rebates': ['__init__.py', 'rebate_manager.py', 'rebate_strategies.py']
    }

    # Create the base directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"Created directory: {base_dir}")

    # Create subdirectories and files
    for directory, files in structure.items():
        # Create full directory path
        dir_path = os.path.join(base_dir, directory) if directory else base_dir

        # Create directory if it doesn't exist
        if directory and not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created directory: {dir_path}")

        # Create files
        for file in files:
            file_path = os.path.join(dir_path, file)
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    # Add a simple comment to each file
                    module_name = os.path.splitext(file)[0]
                    if module_name == '__init__':
                        f.write('# Initialize the module\n')
                    else:
                        f.write(f'# {module_name.replace("_", " ").title()} module\n')
                print(f"Created file: {file_path}")


if __name__ == "__main__":
    create_directory_structure()
    print("Hyperliquid strategy directory structure created successfully!")