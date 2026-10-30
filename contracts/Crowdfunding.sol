// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

/// @title Crowdfunding: all-or-nothing fundraising with automatic refunds
contract Crowdfunding {
    struct Campaign {
        address payable creator;
        string title;
        string description;
        uint256 goal;        // in wei
        uint256 deadline;    // unix timestamp
        uint256 totalRaised; // in wei
        bool claimed;
    }

    uint256 public campaignCount;
    mapping(uint256 => Campaign) public campaigns;
    mapping(uint256 => mapping(address => uint256)) public pledges;

    event CampaignCreated(uint256 indexed id, address indexed creator, string title, uint256 goal, uint256 deadline);
    event Pledged(uint256 indexed id, address indexed backer, uint256 amount);
    event FundsClaimed(uint256 indexed id, uint256 amount);
    event Refunded(uint256 indexed id, address indexed backer, uint256 amount);

    modifier exists(uint256 _id) {
        require(_id > 0 && _id <= campaignCount, "Campaign does not exist");
        _;
    }

    function createCampaign(
        string memory _title,
        string memory _description,
        uint256 _goalInWei,
        uint256 _durationInSeconds
    ) external returns (uint256) {
        require(bytes(_title).length > 0, "Title is required");
        require(_goalInWei > 0, "Goal must be greater than zero");
        require(_durationInSeconds > 0, "Duration must be greater than zero");

        campaignCount++;
        uint256 deadline = block.timestamp + _durationInSeconds;
        campaigns[campaignCount] = Campaign(
            payable(msg.sender), _title, _description, _goalInWei, deadline, 0, false
        );
        emit CampaignCreated(campaignCount, msg.sender, _title, _goalInWei, deadline);
        return campaignCount;
    }

    function pledge(uint256 _id) external payable exists(_id) {
        Campaign storage c = campaigns[_id];
        require(block.timestamp < c.deadline, "Campaign has ended");
        require(msg.value > 0, "Pledge must be greater than zero");

        c.totalRaised += msg.value;
        pledges[_id][msg.sender] += msg.value;
        emit Pledged(_id, msg.sender, msg.value);
    }

    function withdrawFunds(uint256 _id) external exists(_id) {
        Campaign storage c = campaigns[_id];
        require(msg.sender == c.creator, "Only the creator can withdraw");
        require(block.timestamp >= c.deadline, "Campaign is still running");
        require(c.totalRaised >= c.goal, "Goal was not reached");
        require(!c.claimed, "Funds already withdrawn");

        c.claimed = true; // effects before interaction
        uint256 amount = c.totalRaised;
        (bool ok, ) = c.creator.call{value: amount}("");
        require(ok, "Transfer failed");
        emit FundsClaimed(_id, amount);
    }

    function claimRefund(uint256 _id) external exists(_id) {
        Campaign storage c = campaigns[_id];
        require(block.timestamp >= c.deadline, "Campaign is still running");
        require(c.totalRaised < c.goal, "Goal was reached, no refunds");

        uint256 amount = pledges[_id][msg.sender];
        require(amount > 0, "Nothing to refund");

        pledges[_id][msg.sender] = 0; // effects before interaction
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Refund failed");
        emit Refunded(_id, msg.sender, amount);
    }
}
