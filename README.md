# tafu.casa.infra

Infrastructure setup and templates for tafu.casa services.

## Project Structure

- Bases: LXD host configurations and setup scripts
- Templates: VM configuration templates
- Services: Example service configurations

## LXD Host Setup

1. Install requirements:
```bash
sudo apt install ansible
ansible-galaxy collection install community.general
```

2. Run bootstrap:
```bash
ansible-playbook -i localhost, Bases/lxd-vm-base/bootstrap.yml
```

3. Create VMs using one of these methods:

    a. Interactive mode (prompts for all values):
    ```bash
    ansible-playbook -i localhost, Bases/lxd-vm-base/create-vm.yml
    ```

    b. Fully automated with command line:
    ```bash
    ansible-playbook -i localhost, Bases/lxd-vm-base/create-vm.yml -e "vm_name=test-vm cpu_cores=4 memory_gb=8 disk_gb=50 interactive=false"
    ```

    c. Using a vars file (create vm-vars.yml):
    ```bash
    # Example vm-vars.yml contents:
    # vm_name: test-vm
    # cpu_cores: 4
    # memory_gb: 8
    # disk_gb: 50
    # interactive: false
    ```
    
    ```bash
    ansible-playbook -i localhost, Bases/lxd-vm-base/create-vm.yml -e "@vm-vars.yml"
    ```

    d. Mix and match (specify some vars, prompt for others):
    ```bash
    ansible-playbook -i localhost, Bases/lxd-vm-base/create-vm.yml -e "vm_name=test-vm cpu_cores=4"
    ```

ansible-playbook -i 192.168.3.225, Templates/core-template/deploy.yml

ansible-playbook -i 192.168.3.215, Templates/runner-template/deploy.yml
ansible-playbook -i 192.168.3.215, Services/demo-app-service/deploy.yml -e "service_name=demo-app-service-1"
ansible-playbook -i 192.168.3.215, Services/demo-app-service/deploy.yml -e "service_name=demo-app-service-2"

ansible-playbook -i 192.168.3.226, -e "runner=staging" Templates/runner-template/deploy.yml
ansible-playbook -i 192.168.3.226, Services/demo-app-service/deploy.yml -e "service_name=demo-app-service-1"
ansible-playbook -i 192.168.3.226, Services/demo-app-service/deploy.yml -e "service_name=demo-app-service-2"